<script lang="ts">
	import { page } from '$app/state';

	/**
	 * Errors take the whole screen. Rendered inside the shell, a 404 looked
	 * like the app with something missing — which read as a broken page
	 * rather than a page that is not there.
	 */
	const title = $derived(page.status === 404 ? 'Not found' : 'Something went wrong');
	const detail = $derived(
		page.status === 404
			? 'That page does not exist on this box. The library is where the songs are.'
			: (page.error?.message ?? 'The box did not finish that request.')
	);
</script>

<div
	class="fixed inset-0 z-[100] grid place-items-center px-6"
	style="background-color:var(--bg-main); background-image:
		radial-gradient(58vw 58vw at 8% -12%, var(--glow-1), transparent 68%),
		radial-gradient(48vw 48vw at 98% 4%, var(--glow-2), transparent 66%),
		radial-gradient(70vw 60vw at 46% 118%, var(--glow-3), transparent 70%);"
>
	<div class="glass-panel rounded-2xl p-10 max-w-md text-center">
		<div class="text-5xl font-extrabold tracking-tight mb-2">{page.status}</div>
		<h1 class="text-lg font-bold mb-2">{title}</h1>
		<p class="text-sm text-muted mb-6">{detail}</p>
		<a
			href="/"
			class="inline-block px-5 py-2.5 rounded-full bg-accent text-white text-sm font-semibold"
		>Back to the library</a>
	</div>
</div>
