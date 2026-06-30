-- cache_lock.lua
-- Atomic cache-check-or-lock Lua script.
-- Redis executes this as ONE uninterruptible operation.
-- No other client can read/write between our GET and SET.
--
-- KEYS[1] = cache key   (SHA256 hash of the prompt)
-- KEYS[2] = lock key    (cache key + ":lock")
-- ARGV[1] = lock TTL    (seconds before lock auto-expires)
--
-- Returns:
--   <json_string>      → cache HIT  (return cached data)
--   "LOCK_ACQUIRED"    → cache MISS, you got the lock (go call LLM)
--   "LOCK_WAIT"        → another request has the lock (wait and retry)

local cached = redis.call('GET', KEYS[1])
if cached then
    return cached
end

local lock = redis.call('SET', KEYS[2], '1', 'NX', 'EX', ARGV[1])
if lock then
    return 'LOCK_ACQUIRED'
end

return 'LOCK_WAIT'
