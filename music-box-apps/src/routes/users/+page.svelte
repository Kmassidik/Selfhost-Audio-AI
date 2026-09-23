<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import TopBar from '$lib/components/TopBar.svelte';

	/**
	 * The register. It says how many accounts exist, who they are, and lets the
	 * admin add one, reset a password or remove someone. There is no sign-up
	 * anywhere else on this box.
	 */
	let { data } = $props();

	let username = $state('');
	let password = $state('');
	let role = $state('member');
	let message = $state('');
	let bad = $state(false);
	let busy = $state(false);
	let resetting = $state<string | null>(null);
	let new_password = $state('');
	let confirming = $state<string | null>(null);

	async function call(path: string, options: RequestInit) {
		const r = await fetch(path, {
			...options,
			headers: { 'Content-Type': 'application/json', ...(options.headers as object) }
		});
		if (!r.ok) {
			const body = await r.json().catch(() => ({}));
			throw new Error(body.message || body.detail || 'that did not work');
		}
		return r.json().catch(() => ({}));
	}

	async function add() {
		busy = true;
		message = '';
		bad = false;
		try {
			await call('/api/users', { method: 'POST', body: JSON.stringify({ username, password, role }) });
			username = '';
			password = '';
			role = 'member';
			await invalidateAll();
			message = 'Added.';
		} catch (e) {
			message = (e as Error).message;
			bad = true;
		} finally {
			busy = false;
		}
	}

	async function save_password(id: string) {
		busy = true;
		try {
			await call(`/api/users/${id}`, { method: 'PATCH', body: JSON.stringify({ password: new_password }) });
			resetting = null;
			new_password = '';
			message = 'Password changed.';
			bad = false;
		} catch (e) {
			message = (e as Error).message;
			bad = true;
		} finally {
			busy = false;
		}
	}

	async function remove(id: string) {
		busy = true;
		try {
			await call(`/api/users/${id}`, { method: 'DELETE' });
			confirming = null;
			await invalidateAll();
			message = 'Removed.';
			bad = false;
		} catch (e) {
			message = (e as Error).message;
			bad = true;
		} finally {
			busy = false;
		}
	}
</script>

<TopBar user={data.user} is_admin>
</TopBar>

<main class="mx-auto max-w-6xl px-6 md:px-8 pt-5 pb-24">
	<header class="mb-5">
		<h1 class="text-3xl md:text-4xl font-extrabold tracking-tight">Users</h1>
		<p class="text-xs md:text-sm text-muted mt-1">
			{data.total} account{data.total === 1 ? '' : 's'} on this box. Admins and members can both make songs;
			only an admin manages accounts.
		</p>
	</header>

	<div class="grid gap-6 lg:grid-cols-[380px_1fr] lg:items-start">
		<section class="glass-panel rounded-2xl p-5">
			<h2 class="text-sm font-bold text-muted mb-3">Add an account</h2>
			<div class="flex flex-col gap-3">
				<input bind:value={username} placeholder="username" autocomplete="off"
					class="w-full bg-glasshover border border-line rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
				<input bind:value={password} type="password" placeholder="password (8+)" autocomplete="new-password"
					class="w-full bg-glasshover border border-line rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
				<div class="flex gap-3">
					<select bind:value={role}
						class="flex-1 bg-glasshover border border-line rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent">
						<option value="member">member</option>
						<option value="admin">admin</option>
					</select>
					<button class="px-5 py-2 rounded-full bg-accent text-white text-sm font-semibold disabled:opacity-50"
						disabled={busy || !username.trim() || password.length < 8} onclick={add}>Add</button>
				</div>
			</div>
			{#if message}<p class="text-xs mt-3 {bad ? 'text-accent' : 'text-muted'}">{message}</p>{/if}
			<p class="text-[11px] text-muted mt-3">
				There is no sign-up page anywhere on this box: an account exists because it was added here.
			</p>
		</section>

		<section class="grid gap-3 sm:grid-cols-2">
			{#each data.items as person (person.id)}
				<div class="glass-panel rounded-xl p-4">
					<div class="flex items-center gap-3">
						<span class="w-8 h-8 shrink-0 rounded-full bg-accent text-white grid place-items-center text-xs font-bold">
							{person.username.slice(0, 1).toUpperCase()}
						</span>
						<span class="font-medium truncate">{person.username}</span>
						<span class="ml-auto rounded-full border border-line px-2 py-0.5 text-[10px]">{person.role}</span>
					</div>
					<div class="text-[11px] text-muted mt-2">added {person.created_at.replace('T', ' ')}</div>
					<div class="flex items-center gap-3 mt-3 text-[11px]">
						<button class="text-muted hover:text-ink" onclick={() => (resetting = resetting === person.id ? null : person.id)}>
							Reset password
						</button>
						{#if confirming === person.id}
							<button class="text-accent font-semibold" disabled={busy} onclick={() => remove(person.id)}>Really remove</button>
							<button class="text-muted" onclick={() => (confirming = null)}>Keep</button>
						{:else}
							<button class="text-muted hover:text-accent" onclick={() => (confirming = person.id)}>Remove</button>
						{/if}
					</div>
					{#if resetting === person.id}
						<div class="flex gap-2 mt-3">
							<input bind:value={new_password} type="password" placeholder="new password (8+)"
								class="flex-1 bg-glasshover border border-line rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
							<button class="px-4 py-2 rounded-full bg-accent text-white text-xs font-semibold disabled:opacity-50"
								disabled={busy || new_password.length < 8} onclick={() => save_password(person.id)}>Save</button>
						</div>
					{/if}
				</div>
			{/each}
		</section>
	</div>
</main>
