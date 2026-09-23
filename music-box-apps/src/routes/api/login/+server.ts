import { json, error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { SESSION_COOKIE, check_password, open_session } from '$lib/server/session.js';
import type { RequestHandler } from './$types';

/**
 * Sign in with a username and a password. Nothing else: no email, no provider,
 * no sign-up form. The account exists because it was made on the box.
 */
export const POST: RequestHandler = async ({ request, cookies, locals }) => {
	const body = (await request.json().catch(() => ({}))) as { username?: string; password?: string };
	if (!body.username?.trim() || !body.password) throw error(400, 'a username and a password');

	const person = await check_password(locals.sql, body.username.trim(), body.password);
	if (!person) throw error(401, 'wrong username or password');

	const { id, expires } = await open_session(locals.sql, person);
	cookies.set(SESSION_COOKIE, id, {
		path: '/',
		httpOnly: true,
		sameSite: 'lax',
		// see hooks.server.ts: plain http on the LAN, so not Secure yet
		secure: env.COOKIE_SECURE === 'true',
		expires
	});
	return json({ username: person.username, role: person.role });
};
