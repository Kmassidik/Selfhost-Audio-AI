<script lang="ts">
	import { goto } from '$app/navigation';

	/**
	 * Sign in. One whitelisted account exists on this box; the server refuses
	 * any other address, so a wrong email is a hint about nothing.
	 */
	let username = $state('');
	let password = $state('');
	let busy = $state(false);
	let message = $state('');

	/** only a path on this box is ever followed, never another host */
	const next = $derived.by(() => {
		const asked = new URLSearchParams(location.search).get('next') ?? '/create';
		return asked.startsWith('/') && !asked.startsWith('//') ? asked : '/create';
	});

	async function sign_in() {
		busy = true;
		message = '';
		try {
			const r = await fetch('/api/login', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password })
			});
			if (!r.ok) throw new Error(r.status === 401 ? 'Wrong username or password.' : 'Could not sign in.');
			goto(next, { invalidateAll: true });
		} catch (e) {
			message = (e as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>Sign in · Dalang Music Box</title></svelte:head>

<div class="w-full max-w-sm mx-auto px-6 py-16">
	<form
		class="glass-panel rounded-2xl p-8 w-full"
		onsubmit={(e) => {
			e.preventDefault();
			sign_in();
		}}
	>
		<div class="flex items-center gap-3 mb-6">
			<span class="w-10 h-10 rounded-xl bg-accent text-white grid place-items-center">
				<i class="ph-fill ph-music-note text-lg"></i>
			</span>
			<div>
				<h1 class="text-lg font-bold leading-tight">Sign in</h1>
				<p class="text-xs text-muted">to make songs on this box</p>
			</div>
		</div>

		<label class="block mb-4">
			<span class="block text-xs font-bold text-muted mb-1">Username</span>
			<input type="text" bind:value={username} autocomplete="username" required
				class="w-full bg-glasshover border border-line rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
		</label>

		<label class="block mb-6">
			<span class="block text-xs font-bold text-muted mb-1">Password</span>
			<input type="password" bind:value={password} autocomplete="current-password" required
				class="w-full bg-glasshover border border-line rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
		</label>

		{#if message}<p class="text-xs text-accent mb-4">{message}</p>{/if}

		<button class="w-full py-2.5 rounded-full bg-accent text-white text-sm font-semibold disabled:opacity-50" disabled={busy}>
			{busy ? 'Signing in…' : 'Sign in'}
		</button>

		<p class="text-[11px] text-muted mt-4">
			Listening, liking and playlists need no account. Only <span class="font-semibold">the owner</span> can sign in and make songs.
		</p>

		<a
			href="/"
			class="mt-5 flex items-center justify-center gap-2 text-xs font-semibold text-muted hover:text-ink"
		>
			<i class="ph ph-arrow-left"></i> Back to the library
		</a>
	</form>
</div>
