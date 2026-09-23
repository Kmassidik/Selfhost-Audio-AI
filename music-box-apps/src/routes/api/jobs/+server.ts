import { json, error } from '@sveltejs/kit';
import { enqueue, queue_depth, recent } from '$lib/db/jobs.js';
import { get_model } from '$lib/server/catalog.js';
import { require_signed_in } from '$lib/server/gate.js';
import { validate_tags } from '$lib/server/tags.js';
import type { RequestHandler } from './$types';

/**
 * /api/jobs — the create page's door to the cards. Writing one costs a card,
 * so it is the owner's alone; so is reading the queue.
 */
export const GET: RequestHandler = async ({ url, locals }) => {
	require_signed_in(locals);
	const limit = Math.max(1, Math.min(Number(url.searchParams.get('limit') ?? 50), 100));
	return json({ items: await recent(locals.sql, limit) });
};

export const POST: RequestHandler = async ({ request, locals }) => {
	require_signed_in(locals);
	const body = (await request.json().catch(() => null)) as {
		model?: string;
		params?: Record<string, unknown>;
		title?: string;
	} | null;
	if (!body?.model) throw error(400, 'a model is required');

	const spec = get_model(body.model);
	if (!spec) throw error(400, `unknown model ${body.model}`);
	if (spec.kind !== 'sing') throw error(400, `${spec.name} does not make music`);

	const params = body.params ?? {};

	// tags are checked here as well as on the page: the page is a convenience,
	// this is the boundary the worker trusts
	if (params.tags !== undefined) {
		const checked = validate_tags(params.tags);
		if (checked.errors.length) throw error(400, `tags: ${checked.errors.join('; ')}`);
		params.tags = checked.tags;
	}
	const missing = (spec as { required?: string[] }).required?.filter((field) => {
		const value = params[field];
		return value === undefined || value === null || String(value).trim() === '';
	});
	if (missing?.length) {
		throw error(400, `${spec.name} needs ${missing.join(', ')} before it can start`);
	}

	// who asked for it: the song carries the name later
	const id = await enqueue(locals.sql, body.model, params, body.title ?? '', locals.user?.username ?? '');
	return json({ id, ...(await queue_depth(locals.sql)) });
};
