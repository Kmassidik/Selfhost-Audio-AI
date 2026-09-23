import type { Handle } from '@sveltejs/kit';
import { randomUUID } from 'node:crypto';
import { db_factory } from '$lib/db/index.js';
import { SESSION_COOKIE, person_for } from '$lib/server/session.js';
import { env } from '$env/dynamic/private';

/**
 * One middleware, per request. It answers two questions: who is signed in
 * (the owner, for making songs) and which anonymous listener this browser is
 * (for likes and playlists, which need no account at all).
 */
const LISTENER_COOKIE = 'dalang_listener';

export const handle: Handle = async ({ event, resolve }) => {
	event.locals.sql = db_factory(env);
	event.locals.user = await person_for(event.locals.sql, event.cookies.get(SESSION_COOKIE) ?? '');

	let listener = event.cookies.get(LISTENER_COOKIE) ?? '';
	if (!listener) {
		listener = randomUUID();
		event.cookies.set(LISTENER_COOKIE, listener, {
			path: '/',
			httpOnly: true,
			sameSite: 'lax',
			// Secure by default would make the browser drop this cookie over
			// plain http, which is what this box is: the LAN address, no TLS.
			secure: env.COOKIE_SECURE === 'true',
			maxAge: 60 * 60 * 24 * 365
		});
	}
	event.locals.listener = listener;

	try {
		return await resolve(event);
	} finally {
		await event.locals.sql.end({ timeout: 1 });
	}
};
