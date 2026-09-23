import { counts, top_tags } from '$lib/db/library.js';
import { list_playlists } from '$lib/db/playlists.js';
import { models } from '$lib/server/catalog.js';

/**
 * What the shell needs on every page: the visitor's playlists, the categories
 * that have songs, the counts, and whether the owner is signed in.
 */
export const load = async ({ locals }) => {
	const [categories, stats, playlists] = await Promise.all([
		top_tags(locals.sql),
		counts(locals.sql, locals.listener),
		list_playlists(locals.sql, locals.listener)
	]);
	return {
		categories,
		stats,
		playlists,
		// 'yue2' is an id; 'YuE2' is what a person should read
		model_names: Object.fromEntries(models().map((m) => [m.id, m.name])),
		user: locals.user,
		is_admin: locals.user?.role === 'admin'
	};
};
