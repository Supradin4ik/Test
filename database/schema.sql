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
    stage_size INTEGER,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_id INTEGER,
    part_number TEXT,
    name TEXT,
    metal TEXT,
    thickness REAL,
    qty_per_product INTEGER,
    total_qty INTEGER,
    FOREIGN KEY (type_id) REFERENCES types(id)
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    stage_name TEXT,
    order_index INTEGER,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS type_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_id INTEGER,
    batch_number INTEGER,
    qty_planned INTEGER,
    status TEXT,
    FOREIGN KEY (type_id) REFERENCES types(id)
);

CREATE TABLE IF NOT EXISTS batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER,
    item_id INTEGER,
    qty_required INTEGER,
    qty_completed INTEGER,
    FOREIGN KEY (batch_id) REFERENCES type_batches(id),
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS batch_item_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_item_id INTEGER,
    stage_name TEXT,
    status TEXT,
    FOREIGN KEY (batch_item_id) REFERENCES batch_items(id)
);

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    zone_type TEXT
);

CREATE TABLE IF NOT EXISTS transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER,
    date TEXT,
    location_id INTEGER,
    comment TEXT,
    FOREIGN KEY (batch_id) REFERENCES type_batches(id),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- Operational constraints and temporary stops.
CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_type TEXT,
    object_id INTEGER,
    reason TEXT,
    comment TEXT,
    status TEXT
);
