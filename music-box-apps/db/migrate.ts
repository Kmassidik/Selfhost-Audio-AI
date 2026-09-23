/**
 * migrate.ts — applies every migration in db/migrations once each, recorded
 * in schema_migrations. Run by `bun run db:migrate`.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import postgres from 'postgres';

const here = dirname(fileURLToPath(import.meta.url));
const url = process.env.DATABASE_URL ?? 'postgres://music:music@127.0.0.1:5432/musicbox';
const sql = postgres(url, { idle_timeout: 0 });

await sql`CREATE TABLE IF NOT EXISTS schema_migrations (
	name TEXT PRIMARY KEY, applied_at TEXT NOT NULL
)`;

const applied = new Set(
	(await sql`SELECT name FROM schema_migrations`).map((r: { name: string }) => r.name)
);

const files = readdirSync(join(here, 'migrations'))
	.filter((f) => f.endsWith('.sql'))
	.sort();
for (const f of files) {
	if (applied.has(f)) continue;
	const sql_text = readFileSync(join(here, 'migrations', f), 'utf8');
	await sql.begin(async (tx) => {
		await tx.unsafe(sql_text);
		await tx`INSERT INTO schema_migrations (name, applied_at)
		         VALUES (${f}, to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))`;
	});	console.log(`applied ${f}`);
}

await sql.end();
console.log('migrations complete');
