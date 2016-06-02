SELECT "subject", MAX("timestamp") AS "last_timestamp", COUNT(*) AS "posts_count"
FROM "containers"
GROUP BY "subject" HAVING "subject" IS NOT NULL
ORDER BY "last_timestamp" DESC;
