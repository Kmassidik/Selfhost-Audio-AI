import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// Node module adapter; the runtime is Bun inside the container.
		adapter: adapter({ out: 'build' })
	}
};

export default config;
