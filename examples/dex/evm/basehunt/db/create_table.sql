CREATE TABLE IF NOT EXISTS states (
    id INT PRIMARY KEY,
    address TEXT NOT NULL,
    points INT DEFAULT 0,
    referral_code TEXT NOT NULL,
    UNIQUE (address)
)