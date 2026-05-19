USE fmcg_churn;

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS distributors;

CREATE TABLE distributors(
  distributor_id VARCHAR(20) PRIMARY KEY,
  country VARCHAR(100),
  first_seen_date DATE,
  last_seen_date DATE,
  total_orders INT DEFAULT 0,
  total_revenue DECIMAL(12,2) DEFAULT 0.00,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders(
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  invoice_no      VARCHAR(20),
  distributor_id  VARCHAR(20),
  stock_code      VARCHAR(20),
  description     VARCHAR(255),
  quantity        INT,
  invoice_date    DATETIME,
  unit_price      DECIMAL(10,2),
  line_revenue    DECIMAL(12,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
  country         VARCHAR(100),

FOREIGN KEY(distributor_id) REFERENCES distributors(distributor_id),
INDEX idx_distributor(distributor_id),
INDEX idx_invoice_date(invoice_date),
INDEX idx_invoice_no(invoice_no)

);