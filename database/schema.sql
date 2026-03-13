CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    client TEXT,
    deadline TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    type_name TEXT,
    quantity_plan INTEGER,
    stage_size INTEGER
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_id INTEGER,
    part_number TEXT,
    name TEXT,
    metal TEXT,
    thickness REAL,
    qty_per_product INTEGER,
    total_qty INTEGER
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    stage_name TEXT,
    order_index INTEGER
);

CREATE TABLE IF NOT EXISTS stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_id INTEGER,
    stage_name TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    date TEXT,
    location TEXT
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_type TEXT,
    object_id INTEGER,
    action TEXT,
    timestamp TEXT
);
