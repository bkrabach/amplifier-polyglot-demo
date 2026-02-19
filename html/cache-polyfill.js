/**
 * Cache API polyfill — provides an in-memory fallback when the
 * real Cache API is unavailable (file://, tracking prevention,
 * private browsing, etc.).
 * 
 * MUST run BEFORE any WebLLM imports.
 * Trade-off: models re-download every page load when polyfill is active.
 */
(function installCachePolyfill() {
    if (typeof caches !== 'undefined') {
        try {
            caches.open('__probe__').then(function(c) { return c.keys(); }).catch(function() {
                console.warn('[cache-polyfill] Cache API exists but is blocked. Installing fallback.');
                installFallback();
            });
            return;
        } catch (e) {
            // Synchronous throw — install fallback
        }
    }
    
    console.warn('[cache-polyfill] Cache API unavailable. Using in-memory fallback.');
    console.warn('[cache-polyfill] Models will re-download on every page load.');
    installFallback();
    
    function installFallback() {
        var stores = new Map();
        
        function FakeCache() { this._entries = new Map(); }
        FakeCache.prototype.match = function(request) {
            var key = typeof request === 'string' ? request : request.url;
            return Promise.resolve(this._entries.get(key) || undefined);
        };
        FakeCache.prototype.put = function(request, response) {
            var key = typeof request === 'string' ? request : request.url;
            this._entries.set(key, response.clone());
            return Promise.resolve();
        };
        FakeCache.prototype.add = function(request) {
            var self = this;
            return fetch(request).then(function(resp) { return self.put(request, resp); });
        };
        FakeCache.prototype.addAll = function(requests) {
            return Promise.all(requests.map(function(r) { return this.add(r); }.bind(this)));
        };
        FakeCache.prototype.delete = function(request) {
            var key = typeof request === 'string' ? request : request.url;
            return Promise.resolve(this._entries.delete(key));
        };
        FakeCache.prototype.keys = function() {
            return Promise.resolve(Array.from(this._entries.keys()).map(function(url) { return new Request(url); }));
        };
        
        function FakeCacheStorage() {}
        FakeCacheStorage.prototype.open = function(name) {
            if (!stores.has(name)) stores.set(name, new FakeCache());
            return Promise.resolve(stores.get(name));
        };
        FakeCacheStorage.prototype.has = function(name) { return Promise.resolve(stores.has(name)); };
        FakeCacheStorage.prototype.delete = function(name) { return Promise.resolve(stores.delete(name)); };
        FakeCacheStorage.prototype.keys = function() { return Promise.resolve(Array.from(stores.keys())); };
        FakeCacheStorage.prototype.match = function(request) {
            var allCaches = Array.from(stores.values());
            return allCaches.reduce(function(p, cache) {
                return p.then(function(hit) { return hit || cache.match(request); });
            }, Promise.resolve(undefined));
        };
        
        window.caches = new FakeCacheStorage();
        if (typeof self !== 'undefined') self.caches = window.caches;
    }
})();
