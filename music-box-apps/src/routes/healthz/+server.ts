import { counts } from '$lib/db/library.js';
import { json } from '@sveltejs/kit';

/**
 * healthz — one reply that says what is alive: the database, the app's own
 * library count. No metrics stack, as decided in the PRD.
 */
export async function GET({ locals }) {
	try {
		const c = await counts(locals.sql);
		return json({ ok: true, songs: c.songs, seconds: c.seconds });
	} catch (e) {
		return json({ ok: false, error: String(e).slice(0, 200) }, { status: 503 });
	}
}
