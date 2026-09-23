import { json } from '@sveltejs/kit';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { counts } from '$lib/db/library.js';
import { queue_depth } from '$lib/db/jobs.js';
import { require_signed_in } from '$lib/server/gate.js';
import type { RequestHandler } from './$types';

const run = promisify(execFile);

/**
 * /api/status — the queue and the cards, for the create page's gauges.
 * Owner-only: card memory is not a visitor's business.
 */
export const GET: RequestHandler = async ({ locals }) => {
	require_signed_in(locals);

	const cards: { used: number; total: number; util: number }[] = [];
	try {
		const { stdout } = await run(
			'nvidia-smi',
			['--query-gpu=memory.used,memory.total,utilization.gpu', '--format=csv,noheader,nounits'],
			{ timeout: 5000 }
		);
		for (const line of stdout.trim().split('\n')) {
			const [used, total, util] = line.split(',').map((n) => Number(n.trim()));
			cards.push({ used: used ?? 0, total: total ?? 0, util: util ?? 0 });
		}
	} catch {
		// no cards visible from this container is not a failure worth raising
	}

	return json({ cards, ...(await queue_depth(locals.sql)), ...(await counts(locals.sql)) });
};
