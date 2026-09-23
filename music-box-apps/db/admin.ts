/**
 * Make or update the owner's account, from the box's own environment. This is
 * the whole of "registration": there is no sign-up page and no email to
 * collect.
 *
 *   ADMIN_USERNAME=... ADMIN_PASSWORD=... bun run db:owner
 */
import postgres from 'postgres';
import { create_user } from '../src/lib/server/session.js';

const url = process.env.DATABASE_URL ?? 'postgres://music:music@127.0.0.1:5432/musicbox';
const username = (process.env.ADMIN_USERNAME ?? '').trim();
const password = process.env.ADMIN_PASSWORD ?? '';

if (!username || password.length < 8) {
	console.error('set ADMIN_USERNAME and ADMIN_PASSWORD (at least 8 characters)');
	process.exit(1);
}

const sql = postgres(url, { max: 1 });
const person = await create_user(sql, username, password, 'admin');
console.log(`admin ready: ${person.username} (${person.role})`);
await sql.end();
