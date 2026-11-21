/** @type {import('tailwindcss').Config} */
export default {content:['./index.html','./src/**/*.{ts,tsx}'],theme:{extend:{fontFamily:{sans:['Manrope Variable','Arial','sans-serif'],mono:['JetBrains Mono Variable','Consolas','monospace']},colors:{ink:'var(--ink)',muted:'var(--muted)',line:'var(--line)',surface:'var(--surface)',accent:'var(--accent)',pale:'var(--pale)'}}},plugins:[]};
