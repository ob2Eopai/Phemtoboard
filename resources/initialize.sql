CREATE TABLE IF NOT EXISTS "containers" (
	"link" TEXT NOT NULL PRIMARY KEY,
	"origin" TEXT NOT NULL,
	"timestamp" REAL NOT NULL,
	"subject" TEXT,
	"message" TEXT,
	"attachment_ID" BLOB,
	"attachment_type" TEXT
);

CREATE INDEX IF NOT EXISTS "timestamp" ON "containers" ("timestamp");
CREATE INDEX IF NOT EXISTS "subject" ON "containers" ("subject");
