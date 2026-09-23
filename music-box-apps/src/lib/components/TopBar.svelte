<script lang="ts">
	/**
	 * The bar on the pages that are not the studio. It sits in the flow — no
	 * sticky, no absolute — inside a centred column, so it lines up with the
	 * content under it and cannot overlap anything.
	 */
	let {
		user = null,
		is_admin = false,
		children
	} = $props<{
		user: { username: string; role: string } | null;
		is_admin?: boolean;
		children?: import('svelte').Snippet;
	}>();

	async function sign_out() {
		await fetch('/api/logout', { method: 'POST' });
		location.href = '/';
	}
</script>

<header class="border-b border-line">
	<div class="mx-auto max-w-6xl px-6 md:px-8 py-4 flex items-center gap-4">
		<a href="/" class="flex items-center gap-2.5 shrink-0" title="Dalang Music Box">
			<span class="w-7 h-7 rounded-lg bg-accent text-white grid place-items-center">
				<i class="ph-fill ph-music-note text-xs"></i>
			</span>
			<span class="font-bold tracking-tight">Dalang Music Box</span>
		</a>

		<div class="ml-auto flex items-center gap-3 md:gap-4 shrink-0">
			{@render children?.()}
			{#if is_admin}
				<a href="/users" class="text-muted hover:text-ink p-1" title="Users">
					<i class="ph ph-users text-base"></i>
				</a>
			{/if}
			{#if user}
				<span class="w-7 h-7 rounded-full bg-accent text-white grid place-items-center text-[11px] font-bold" title={user.username}>
					{user.username.slice(0, 1).toUpperCase()}
				</span>
				<button class="text-muted hover:text-accent p-1" title="Sign out" onclick={sign_out}>
					<i class="ph ph-sign-out text-base"></i>
				</button>
			{/if}
		</div>
	</div>
</header>
