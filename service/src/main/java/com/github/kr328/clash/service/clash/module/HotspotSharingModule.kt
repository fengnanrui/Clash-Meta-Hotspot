package com.github.kr328.clash.service.clash.module

import android.app.Service
import android.os.Process
import com.github.kr328.clash.common.log.Log
import com.github.kr328.clash.service.store.ServiceStore
import kotlinx.coroutines.*
import java.io.File
import java.text.DateFormat
import java.util.Date

/** A root shell owns only this session's routes/chains and cleans them when the lease disappears. */
class HotspotSharingModule(service: Service) : Module<Unit>(service) {
    override suspend fun run() = coroutineScope {
        val store = ServiceStore(service)
        var session: Job? = null
        var previous = false
        try {
            while (isActive) {
                val enabled = store.hotspotSharing
                if (enabled != previous) {
                    session?.cancelAndJoin()
                    session = if (enabled) launch { runSession() } else null
                    previous = enabled
                }
                delay(500)
            }
        } finally {
            withContext(NonCancellable) { session?.cancelAndJoin() }
        }
    }

    private suspend fun runSession() = coroutineScope {
        val store = ServiceStore(service)
        val lease = File.createTempFile("hotspot-", ".lease", service.filesDir)
        val script = File(service.filesDir, "hotspot-sharing.sh")
        var process: java.lang.Process? = null
        fun status(message: String) {
            store.hotspotSharingStatus = "${DateFormat.getTimeInstance().format(Date())}: $message"
            Log.i("Hotspot sharing: $message")
        }
        try {
            val iface = store.hotspotInterface
            require(iface.isEmpty() || iface.matches(Regex("[a-zA-Z0-9_.-]{1,15}"))) {
                "Invalid hotspot interface"
            }
            withContext(Dispatchers.IO) {
                service.assets.open("hotspot-sharing.sh").use { input ->
                    script.outputStream().use { output -> input.copyTo(output) }
                }
            }
            status("Requesting root / 正在请求 root")
            // Paths come from the app's private files directory; never interpolate user shell code.
            fun quote(value: String) = "'" + value.replace("'", "'\\''") + "'"
            val command = listOf("sh", quote(script.path), Process.myPid().toString(),
                quote(lease.path), quote(iface)).joinToString(" ")
            val shell = withContext(Dispatchers.IO) {
                ProcessBuilder("su", "-c", command).redirectErrorStream(true).start()
            }
            process = shell
            val reader = launch(Dispatchers.IO) {
                shell.inputStream.bufferedReader().useLines { lines ->
                    lines.forEach { line ->
                        if (line.startsWith("CMFA_STATUS: ")) status(line.removePrefix("CMFA_STATUS: "))
                        else Log.w("Hotspot root: $line")
                    }
                }
            }
            try {
                while (isActive && reader.isActive) delay(500)
                reader.join()
                val result = withContext(Dispatchers.IO) { shell.waitFor() }
                status("Stopped (exit $result). Check root authorization and logs / 已停止，请检查 root 授权和日志")
            } finally {
                lease.delete()
                // The root watchdog checks both this lease and the service PID, including on crashes.
                withContext(NonCancellable) {
                    withTimeoutOrNull(10_000) { reader.join() }
                }
                reader.cancel()
            }
        } catch (e: CancellationException) {
            status("Stopped / 已停止")
            throw e
        } catch (e: Exception) {
            status("Failed / 失败: ${e.message}")
        } finally {
            lease.delete()
            process?.destroy()
        }
    }
}
