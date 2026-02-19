// typescript/web-research.ts
// Web research tool — browser-native fetch using CORS-friendly APIs.
// Uses Wikipedia (search + page summaries) and GitHub (repo search).
// No CORS proxy needed — these APIs support cross-origin requests natively.

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
                return await searchWikipediaAndGitHub(input.query || "");
            case "fetch":
                return await fetchWikipediaSummary(input.query || input.url || "");
            case "extract_links":
                return await searchGitHub(input.query || input.url || "");
            default:
                return { success: false, error: "Unknown action: " + input.action };
        }
    } catch (e: any) {
        return { success: false, error: e.message || String(e) };
    }
}

async function searchWikipediaAndGitHub(query: string): Promise<ToolResult> {
    if (!query) return { success: false, error: "query is required" };

    // Search Wikipedia (CORS-friendly with origin=*)
    var wikiResults: any[] = [];
    try {
        var wikiUrl = "https://en.wikipedia.org/w/api.php?action=opensearch&search=" +
            encodeURIComponent(query) + "&limit=5&format=json&origin=*";
        var wikiResp = await fetch(wikiUrl);
        var wikiData = await wikiResp.json();
        // OpenSearch returns [query, [titles], [descriptions], [urls]]
        if (wikiData && wikiData.length >= 4) {
            for (var i = 0; i < wikiData[1].length; i++) {
                wikiResults.push({
                    title: wikiData[1][i],
                    description: wikiData[2][i] || "",
                    url: wikiData[3][i] || ""
                });
            }
        }
    } catch (e: any) {
        // Wikipedia search failed, continue with GitHub
    }

    // Search GitHub repos (CORS-friendly)
    var githubResults: any[] = [];
    try {
        var ghUrl = "https://api.github.com/search/repositories?q=" +
            encodeURIComponent(query) + "&per_page=5&sort=stars";
        var ghResp = await fetch(ghUrl);
        var ghData = await ghResp.json();
        githubResults = (ghData.items || []).map(function(repo: any) {
            return {
                name: repo.full_name,
                description: repo.description || "",
                url: repo.html_url,
                stars: repo.stargazers_count,
                language: repo.language
            };
        });
    } catch (e: any) {
        // GitHub search failed, continue with what we have
    }

    return {
        success: true,
        output: JSON.stringify({
            wikipedia: wikiResults,
            github: githubResults,
            total_results: wikiResults.length + githubResults.length
        })
    };
}

async function fetchWikipediaSummary(topic: string): Promise<ToolResult> {
    if (!topic) return { success: false, error: "query/url is required" };

    // Clean up the topic for Wikipedia URL
    var pageName = topic.replace(/^https?:\/\/.*\/wiki\//, "").replace(/ /g, "_");

    try {
        var url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + encodeURIComponent(pageName);
        var resp = await fetch(url);
        var data = await resp.json();

        return {
            success: true,
            output: JSON.stringify({
                title: data.title || topic,
                extract: data.extract || "No content found",
                description: data.description || "",
                url: data.content_urls ? data.content_urls.desktop.page : "",
                length: (data.extract || "").length
            })
        };
    } catch (e: any) {
        return { success: false, error: "Failed to fetch Wikipedia summary: " + e.message };
    }
}

async function searchGitHub(query: string): Promise<ToolResult> {
    if (!query) return { success: false, error: "query is required" };

    try {
        var url = "https://api.github.com/search/repositories?q=" +
            encodeURIComponent(query) + "&per_page=10&sort=stars";
        var resp = await fetch(url);
        var data = await resp.json();

        var repos = (data.items || []).map(function(repo: any) {
            return {
                name: repo.full_name,
                description: repo.description || "",
                url: repo.html_url,
                stars: repo.stargazers_count,
                language: repo.language,
                topics: repo.topics || []
            };
        });

        return {
            success: true,
            output: JSON.stringify({
                repos: repos,
                total: data.total_count || repos.length
            })
        };
    } catch (e: any) {
        return { success: false, error: "Failed to search GitHub: " + e.message };
    }
}

// Register globally for the JavaScript bridge
(window as any).tsWebResearch = tsWebResearch;
