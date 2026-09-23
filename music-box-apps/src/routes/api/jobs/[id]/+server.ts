import { json, error } from '@sveltejs/kit';
import { cancel, queue_depth } from '$lib/db/jobs.js';
import { require_signed_in } from '$lib/server/gate.js';
import type { RequestHandler } from './$types';

/**
 * /api/jobs/{id} — take a waiting job out of the line. A job already running
 * belongs to the cards; stopping it half-way leaves a part-written file.
 */
export const DELETE: RequestHandler = async ({ params, locals }) => {
	require_signed_in(locals);
	const id = Number(params.id);
	if (!Number.isInteger(id)) throw error(400, 'a job id is a number');

	if (!(await cancel(locals.sql, id))) throw error(409, 'that job has already started');
	return json({ cancelled: id, ...(await queue_depth(locals.sql)) });
};
