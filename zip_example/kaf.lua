-- Stand-in for the Kindle UI's "framework started" signal (com.lab126.kaf frameworkStarted=1).
-- With the UI stopped, powerd ignores the power button and never enters screensaver until
-- something publishes this; KOReader's no-framework mode does the same. Runs until killed.
local ok, lipc = pcall(require, "liblipclua")
if not ok then io.stderr:write("no liblipclua\n") os.exit(1) end
local h = lipc.init("com.lab126.kaf")
if not h then io.stderr:write("lipc.init failed\n") os.exit(1) end
local p = h:register_int_property("frameworkStarted", "r")
p.value = 1
-- If the UI's screensaver/splash drawer (blanket) is running, stop it painting over us.
pcall(function() h:set_string_property("com.lab126.blanket", "unload", "splash") end)
pcall(function() h:set_string_property("com.lab126.blanket", "unload", "screensaver") end)
while true do os.execute("sleep 3600") end
