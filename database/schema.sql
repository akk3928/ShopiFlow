
-- =========================================================
-- ShopiFlow Database Schema
-- AI/ML Business Intelligence & Retail Management System
-- PostgreSQL
-- =========================================================


-- =========================================================
-- 1. CUSTOMERS
-- =========================================================

CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    customer_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) UNIQUE,
    phone VARCHAR(20),
    address VARCHAR(250),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- 2. PRODUCTS
-- =========================================================

CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL,
    category VARCHAR(100) NOT NULL,
    sku VARCHAR(50) UNIQUE NOT NULL,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    cost_price NUMERIC(10, 2) NOT NULL CHECK (cost_price >= 0),
    supplier VARCHAR(150),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- 3. INVENTORY
-- =========================================================

CREATE TABLE IF NOT EXISTS inventory (
    inventory_id SERIAL PRIMARY KEY,
    product_id INTEGER UNIQUE NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    reorder_level INTEGER NOT NULL DEFAULT 10 CHECK (reorder_level >= 0),
    reorder_quantity INTEGER NOT NULL DEFAULT 50 CHECK (reorder_quantity > 0),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_inventory_product
        FOREIGN KEY (product_id)
        REFERENCES products(product_id)
        ON DELETE CASCADE
);


-- =========================================================
-- 4. SALES
-- =========================================================

CREATE TABLE IF NOT EXISTS sales (
    sale_id SERIAL PRIMARY KEY,
    customer_id INTEGER,
    total_amount NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0),
    payment_method VARCHAR(50) NOT NULL,
    sale_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_sales_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id)
        ON DELETE SET NULL
);


-- =========================================================
-- 5. SALE ITEMS
-- =========================================================

CREATE TABLE IF NOT EXISTS sale_items (
    sale_item_id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0),

    CONSTRAINT fk_sale_items_sale
        FOREIGN KEY (sale_id)
        REFERENCES sales(sale_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_sale_items_product
        FOREIGN KEY (product_id)
        REFERENCES products(product_id)
        ON DELETE RESTRICT
);


-- =========================================================
-- 6. INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_products_sku
    ON products(sku);

CREATE INDEX IF NOT EXISTS idx_products_category
    ON products(category);

CREATE INDEX IF NOT EXISTS idx_customers_email
    ON customers(email);

CREATE INDEX IF NOT EXISTS idx_sales_customer
    ON sales(customer_id);

CREATE INDEX IF NOT EXISTS idx_sales_date
    ON sales(sale_date);

CREATE INDEX IF NOT EXISTS idx_sale_items_sale
    ON sale_items(sale_id);

CREATE INDEX IF NOT EXISTS idx_sale_items_product
    ON sale_items(product_id);

CREATE INDEX IF NOT EXISTS idx_inventory_product
    ON inventory(product_id);


-- =========================================================
-- 7. SAMPLE PRODUCTS
-- =========================================================

INSERT INTO products
    (product_name, category, sku, price, cost_price, supplier)
VALUES
    ('Milk 1L', 'Dairy', 'SKU001', 60.00, 48.00, 'Local Dairy Supplier'),
    ('Bread', 'Bakery', 'SKU002', 40.00, 30.00, 'Fresh Bakery Supplier'),
    ('Rice 5kg', 'Grocery', 'SKU003', 350.00, 300.00, 'National Foods Supplier'),
    ('Cooking Oil 1L', 'Grocery', 'SKU004', 150.00, 125.00, 'Golden Foods Supplier'),
    ('Biscuits', 'Snacks', 'SKU005', 30.00, 22.00, 'Snack Foods Supplier')
ON CONFLICT (sku) DO NOTHING;


-- =========================================================
-- 8. INITIAL INVENTORY
-- =========================================================

INSERT INTO inventory
    (product_id, quantity, reorder_level, reorder_quantity)
SELECT
    product_id,
    100,
    10,
    50
FROM products
WHERE sku IN ('SKU001', 'SKU002', 'SKU003', 'SKU004', 'SKU005')
ON CONFLICT (product_id) DO NOTHING;

