import { json } from '@sveltejs/kit';
import { SESSION_COOKIE, close_session } from '$lib/server/session.js';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ cookies, locals }) => {
	await close_session(locals.sql, cookies.get(SESSION_COOKIE) ?? '');
	cookies.delete(SESSION_COOKIE, { path: '/' });
	return json({ ok: true });
};
