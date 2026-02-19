// typescript/web-research.ts
// Web research tool — browser-native fetch + DOMParser.
// Called from the Rust WASM kernel via the JavaScript bridge.

interface WebResearchInput {
    action: "search" | "fetch" | "extract_links";
    query?: string;
    url?: string;
    max_length?: number;
    filter?: string;
}

interface ToolResult {
    success: boolean;
    output?: any;
    error?: string;
}

async function tsWebResearch(input: WebResearchInput): Promise<ToolResult> {
    try {
        switch (input.action) {
            case "search":
                return await searchDuckDuckGo(input.query || "");
            case "fetch":
                return await fetchAndExtract(input.url || "", input.max_length || 4000);
            case "extract_links":
                return await extractLinks(input.url || "", input.filter || null);
            default:
                return { success: false, error: `Unknown action: ${input.action}` };
        }
    } catch (e: any) {
        return { success: false, error: e.message || String(e) };
    }
}

async function searchDuckDuckGo(query: string): Promise<ToolResult> {
    if (!query) return { success: false, error: "query is required" };

    // DuckDuckGo Instant Answer API (CORS-friendly)
    const url = `https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json&no_html=1`;
    const response = await fetch(url);
    const data = await response.json();

    const results: any = {
        abstract: data.AbstractText || "",
        abstract_source: data.AbstractSource || "",
        abstract_url: data.AbstractURL || "",
        related_topics: (data.RelatedTopics || []).slice(0, 5).map((t: any) => ({
            text: t.Text || "",
            url: t.FirstURL || "",
        })),
        answer: data.Answer || "",
    };

    return {
        success: true,
        output: results,
    };
}

async function fetchAndExtract(url: string, maxLength: number): Promise<ToolResult> {
    if (!url) return { success: false, error: "url is required" };

    const response = await fetch(url);
    const html = await response.text();

    // Use DOMParser to extract text content
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");

    // Remove script, style, and navigational elements
    doc.querySelectorAll("script, style, nav, header, footer").forEach(el => el.remove());

    // Extract main content
    const main = doc.querySelector("main, article, .content, #content, body");
    let text = (main?.textContent || doc.body?.textContent || "").trim();

    // Clean up whitespace
    text = text.replace(/\s+/g, " ").trim();

    const fullLength = text.length;
    const truncated = fullLength > maxLength;

    // Truncate
    if (truncated) {
        text = text.substring(0, maxLength) + "... [truncated]";
    }

    return {
        success: true,
        output: { content: text, url, length: fullLength, truncated },
    };
}

async function extractLinks(url: string, filter: string | null): Promise<ToolResult> {
    if (!url) return { success: false, error: "url is required" };

    const response = await fetch(url);
    const html = await response.text();

    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");

    let links: any[] = [];
    doc.querySelectorAll("a[href]").forEach(a => {
        const href = a.getAttribute("href");
        const text = a.textContent?.trim();
        if (href && text && !href.startsWith("#") && !href.startsWith("javascript:")) {
            links.push({ text: text.substring(0, 100), url: href });
        }
    });

    if (filter) {
        links = links.filter(l => l.url.includes(filter) || l.text.includes(filter));
    }

    const total = links.length;
    return {
        success: true,
        output: { links: links.slice(0, 20), total },
    };
}

// Export for the JavaScript bridge
(window as any).tsWebResearch = tsWebResearch;
