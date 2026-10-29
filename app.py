                                            if not db.query(Customer).filter(Customer.customer_id == customer_id).first():
                                                raise ValueError(f"Customer ID {customer_id} does not exist.")
                                    lines, total = [], 0.0
                                    for _, row in group.iterrows():
                                        sku = str(row["sku"]).strip()
                                        product = db.query(Product).filter(Product.sku == sku, Product.is_active.is_(True)).first()
                                        if not product:
                                            raise ValueError(f"SKU not found: {sku}")
                                        q = int(row["quantity"])
                                        subtotal = float(product.price or 0) * q
                                        total += subtotal
                                        lines.append((product, q, subtotal))
                                    sale = Sale(customer_id=customer_id, total_amount=total,
                                        payment_method=str(group.iloc[0]["payment_method"])[:50],
                                        sale_date=pd.to_datetime(group.iloc[0]["sale_date"]).to_pydatetime())
                                    db.add(sale)
                                    db.flush()
                                    for product, q, subtotal in lines:
                                        db.add(SaleItem(sale_id=sale.sale_id, product_id=product.product_id,
                                            quantity=q, unit_price=product.price, subtotal=subtotal))
                                    db.commit()
                                    imported += 1
                                except Exception as exc:
                                    db.rollback()
                                    errors.append(f"Order {order_id}: {exc}")
                            st.success(f"Imported {imported} transaction(s).")
                            if errors:
                                st.warning("Some transactions were skipped:\n" + "\n".join(errors[:15]))
                            st.rerun()
            except Exception as exc:
                st.error(f"Could not read sales CSV: {exc}")

    # ========================================================
    # AI PREDICTIONS
    # ========================================================
    elif page == "AI Predictions":
        if not require_role("admin", "manager"):
            st.stop()
        st.title("AI/ML predictions")
        st.caption("Random Forest baseline for sales forecasting and descriptive inventory demand.")
        daily = make_daily_sales(db)
        if daily.empty or len(daily) < 5:
            st.warning("At least 5 distinct sales days are recommended. Import historical sales to build a useful training set.")
        else:
            daily = daily.sort_values("Date").copy()
            daily["day_of_week"] = daily["Date"].dt.dayofweek
            daily["month"] = daily["Date"].dt.month
            daily["day"] = daily["Date"].dt.day
            daily["lag_1"] = daily["Revenue (INR)"].shift(1)
            training = daily.dropna(subset=["lag_1"])
            if len(training) >= 4:
                X = training[["day_of_week", "month", "day", "lag_1"]]
                y = training["Revenue (INR)"]
                model = RandomForestRegressor(n_estimators=150, random_state=42)
                model.fit(X, y)
                future_rows = []
                last_date = daily["Date"].max()
                last_revenue = float(daily.iloc[-1]["Revenue (INR)"])
                for step in range(1, 8):
                    future_date = last_date + pd.Timedelta(days=step)
                    features = pd.DataFrame([{"day_of_week": future_date.dayofweek,
                        "month": future_date.month, "day": future_date.day, "lag_1": last_revenue}])
                    prediction = max(0.0, float(model.predict(features)[0]))
                    future_rows.append({"Date": future_date, "Predicted Revenue (INR)": prediction,
                        currency_label("Predicted Revenue"): convert_from_inr(prediction)})
                    last_revenue = prediction
                forecast = pd.DataFrame(future_rows)
                forecast_col = currency_label("Predicted Revenue")
                st.subheader("Seven-day sales forecast")
                st.info("Educational baseline only. Forecast accuracy depends on the amount and quality of historical data.")
                st.metric(f"Forecast total ({CURRENCY_CODE})", f"{CURRENCY_SYMBOL}{forecast[forecast_col].sum():,.2f}")
                hist = daily[["Date", "Revenue (INR)"]].copy()
                hist["Revenue"] = hist["Revenue (INR)"].apply(convert_from_inr)
                hist["Type"] = "Historical"
                pred = forecast[["Date", forecast_col]].rename(columns={forecast_col: "Revenue"})
                pred["Type"] = "Forecast"
                combined = pd.concat([hist[["Date", "Revenue", "Type"]], pred[["Date", "Revenue", "Type"]],], ignore_index=True)
                st.plotly_chart(px.line(combined, x="Date", y="Revenue", color="Type",
                    markers=True, title=f"Historical and forecast revenue ({CURRENCY_CODE})",
                    template=PLOTLY_TEMPLATE), use_container_width=True)
                display = forecast[["Date", forecast_col]].rename(columns={forecast_col: f"Predicted Revenue ({CURRENCY_CODE})"})
                st.dataframe(display, use_container_width=True, hide_index=True)
                st.download_button("Download forecast CSV", display.to_csv(index=False).encode("utf-8"),
                    "shopiflow_sales_forecast.csv", "text/csv")
            else:
                st.info("More distinct sales days are needed.")

        st.divider()
        st.subheader("Inventory demand and reorder suggestions")
        demand_rows = db.query(
            Product.product_id, Product.product_name, Product.sku,
            Inventory.quantity, Inventory.reorder_level, Inventory.reorder_quantity,
            func.date(Sale.sale_date).label("sale_day"),
            func.sum(SaleItem.quantity).label("units_sold")
        ).join(Inventory, Inventory.product_id == Product.product_id).outerjoin(
            SaleItem, SaleItem.product_id == Product.product_id
        ).outerjoin(Sale, Sale.sale_id == SaleItem.sale_id).filter(
            Product.is_active.is_(True)
        ).group_by(Product.product_id, Product.product_name, Product.sku,
            Inventory.quantity, Inventory.reorder_level, Inventory.reorder_quantity,
            func.date(Sale.sale_date)).all()
        if not demand_rows:
            st.info("Add products and sales to see product demand.")
        else:
            demand_df = pd.DataFrame([{
                "Product": r.product_name, "SKU": r.sku, "Current Stock": int(r.quantity),
                "Reorder Level": int(r.reorder_level), "Reorder Quantity": int(r.reorder_quantity),
                "Date": r.sale_day, "Units Sold": int(r.units_sold or 0)
            } for r in demand_rows])
            by_product = demand_df.groupby(["Product", "SKU", "Current Stock",
                "Reorder Level", "Reorder Quantity"], as_index=False).agg(
                {"Units Sold": "sum", "Date": "nunique"})
            by_product = by_product.rename(columns={"Date": "Days with sales"})
            by_product["Average units/day"] = (by_product["Units Sold"] /
                by_product["Days with sales"].clip(lower=1)).round(2)
            by_product["Suggested reorder"] = (by_product["Reorder Level"] +
                by_product["Reorder Quantity"] - by_product["Current Stock"]).clip(lower=0)
            by_product["Status"] = by_product.apply(
                lambda r: "Low Stock" if r["Current Stock"] <= r["Reorder Level"] else "In Stock", axis=1)
            st.dataframe(by_product.sort_values(["Status", "Current Stock"]),
                use_container_width=True, hide_index=True)
            st.caption("Demand figures are descriptive; per-product ML needs sufficient dated sales history.")

finally:
