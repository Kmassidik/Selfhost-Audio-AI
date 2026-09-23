import { redirect } from '@sveltejs/kit';
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { outcomes } from '$lib/server/catalog.js';
import { max_tags, tag_groups } from '$lib/server/tags.js';

/** Making songs belongs to the owner; anyone else signs in first. */
export const load = async ({ locals }) => {
	if (!locals.user) throw redirect(303, '/login?next=/create');
	// the backgrounds a creator may choose from; if none is chosen the worker
	// picks one by the song's own title
	let assets: string[] = [];
	try {
		assets = readdirSync(join(process.env.DATA_DIR ?? '/data', 'assets'))
			.filter((f) => f.endsWith('.jpg'))
			.sort();
	} catch {
		assets = [];
	}

	return {
		models: await outcomes(locals.sql),
		user: locals.user,
		assets,
		tag_groups: tag_groups(),
		max_tags: max_tags()
	};
};
