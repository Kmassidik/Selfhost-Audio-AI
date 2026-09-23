import { randomBytes, randomUUID } from 'node:crypto';
import type { Sql } from '$lib/db/index.js';

/**
 * Sessions without a framework. The cookie holds a random id; the row holds
 * who it is and when it dies. Passwords are hashed by Bun's own argon2id, so
 * there is no password library to trust and no email address anywhere.
 */
export const SESSION_COOKIE = 'dalang_session';
const DAYS = 30;

export type Person = { id: string; username: string; role: string };

const now = () => new Date().toISOString().slice(0, 19);

export async function hash_password(password: string): Promise<string> {
	return Bun.password.hash(password, { algorithm: 'argon2id' });
}

export async function create_user(
	sql: Sql,
	username: string,
	password: string,
	role = 'member'
): Promise<Person> {
	const id = randomUUID();
	const hash = await hash_password(password);
	const [row] = await sql<Person[]>`
		INSERT INTO users (id, username, password_hash, role, created_at)
		VALUES (${id}, ${username}, ${hash}, ${role}, ${now()})
		ON CONFLICT (username) DO UPDATE
		  SET password_hash = EXCLUDED.password_hash
		RETURNING id, username, role`;
	return row;
}

/** the password the owner typed, against the hash on the box */
export async function check_password(sql: Sql, username: string, password: string): Promise<Person | null> {
	const [row] = await sql<{ id: string; username: string; role: string; password_hash: string }[]>`
		SELECT id, username, role, password_hash FROM users WHERE username = ${username}`;
	if (!row) return null;
	const ok = await Bun.password.verify(password, row.password_hash).catch(() => false);
	return ok ? { id: row.id, username: row.username, role: row.role } : null;
}

export async function open_session(sql: Sql, user: Person): Promise<{ id: string; expires: Date }> {
	const id = randomBytes(32).toString('hex');
	const expires = new Date(Date.now() + DAYS * 24 * 60 * 60 * 1000);
	await sql`
		INSERT INTO sessions (id, user_id, created_at, expires_at)
		VALUES (${id}, ${user.id}, ${now()}, ${expires.toISOString().slice(0, 19)})`;
	return { id, expires };
}

export async function person_for(sql: Sql, session_id: string): Promise<Person | null> {
	if (!session_id) return null;
	const [row] = await sql<Person[]>`
		SELECT u.id, u.username, u.role
		FROM sessions s JOIN users u ON u.id = s.user_id
		WHERE s.id = ${session_id} AND s.expires_at > ${now()}`;
	return row ?? null;
}

/** everyone on the box: the admin's register */
export async function list_users(sql: Sql): Promise<
	{ id: string; username: string; role: string; created_at: string }[]
> {
	return sql`
		SELECT id, username, role, created_at FROM users ORDER BY created_at ASC`;
}

export async function set_password(sql: Sql, id: string, password: string): Promise<boolean> {
	const hash = await hash_password(password);
	const rows = await sql`UPDATE users SET password_hash = ${hash} WHERE id = ${id} RETURNING id`;
	return rows.length > 0;
}

export async function remove_user(sql: Sql, id: string): Promise<boolean> {
	const rows = await sql`DELETE FROM users WHERE id = ${id} RETURNING id`;
	return rows.length > 0;
}

export async function count_admins(sql: Sql): Promise<number> {
	const [row] = await sql<[{ n: number }]>`SELECT COUNT(*)::int AS n FROM users WHERE role = 'admin'`;
	return row?.n ?? 0;
}

export async function close_session(sql: Sql, session_id: string): Promise<void> {
	if (!session_id) return;
	await sql`DELETE FROM sessions WHERE id = ${session_id}`;
	await sql`DELETE FROM sessions WHERE expires_at < ${now()}`;
}
