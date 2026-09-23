import type { Sql } from './index.js';

/**
 * Anonymous listeners. A visitor gets an id in a cookie and a row here the
 * first time they write something; until then they exist only as an id.
 */
export async function ensure_listener(sql: Sql, id: string): Promise<void> {
	if (!id) return;
	await sql`
		INSERT INTO listeners (id, kind, label, created_at)
		VALUES (${id}, 'anonymous', '', to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
		ON CONFLICT (id) DO NOTHING`;
}
