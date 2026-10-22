package com.example.smartparking

import androidx.compose.ui.geometry.Offset
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

const val LOT_ID = "LOT_A"

// Emulator: 10.0.2.2 is your PC. Real phone: your PC's Wi-Fi IP, e.g. "http://192.168.1.20:5000"
const val BASE_URL = "http://10.0.2.2:5000"

class LotFullException : Exception("Lot is full")

data class LotStatus(val name: String, val total: Int, val free: Int, val freeIds: Set<String>)
data class Bay(val number: Int, val spotId: String, val polygon: List<Offset>)
data class LotMap(val width: Int, val height: Int, val entrance: Offset, val bays: List<Bay>)
data class Assignment(
    val id: Int, val spotId: String, val number: Int,
    val route: List<Offset>, val steps: List<String>,
)

object Api {
    private suspend fun call(method: String, path: String): JSONObject = withContext(Dispatchers.IO) {
        val c = URL(BASE_URL + path).openConnection() as HttpURLConnection
        try {
            c.requestMethod = method
            c.connectTimeout = 4000
            c.readTimeout = 6000
            if (method == "POST") {
                c.doOutput = true
                c.setRequestProperty("Content-Type", "application/json")
                c.outputStream.use { it.write("{}".toByteArray()) }
            }
            val code = c.responseCode
            val stream = if (code in 200..299) c.inputStream else c.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: "{}"
            if (code == 409) throw LotFullException()
            if (code !in 200..299) throw Exception("HTTP $code")
            JSONObject(text)
        } finally {
            c.disconnect()
        }
    }

    private fun JSONArray.points(): List<Offset> = List(length()) { i ->
        val p = getJSONArray(i)
        Offset(p.getDouble(0).toFloat(), p.getDouble(1).toFloat())
    }

    suspend fun status(): LotStatus {
        val j = call("GET", "/api/lots/$LOT_ID/status")
        val arr = j.getJSONArray("spots")
        val ids = HashSet<String>()
        for (i in 0 until arr.length()) {
            val sp = arr.getJSONObject(i)
            if (sp.getString("status") == "vacant") ids.add(sp.getString("spot_id"))
        }
        return LotStatus(j.getString("name"), j.getInt("total"), j.getInt("free"), ids)
    }

    suspend fun map(): LotMap {
        val j = call("GET", "/api/lots/$LOT_ID/map")
        val spots = j.getJSONArray("spots")
        val bays = List(spots.length()) { i ->
            val s = spots.getJSONObject(i)
            Bay(s.getInt("number"), s.getString("spot_id"), s.getJSONArray("polygon").points())
        }
        val e = j.getJSONArray("entrance")
        return LotMap(
            j.getInt("width"), j.getInt("height"),
            Offset(e.getDouble(0).toFloat(), e.getDouble(1).toFloat()), bays,
        )
    }

    suspend fun assign(): Assignment {
        val j = call("POST", "/api/lots/$LOT_ID/assign")
        val st = j.getJSONArray("steps")
        return Assignment(
            j.getInt("assignment_id"), j.getString("spot_id"), j.getInt("number"),
            j.getJSONArray("route").points(), List(st.length()) { st.getString(it) },
        )
    }

    suspend fun confirm(id: Int) {
        call("POST", "/api/assignments/$id/confirm")
    }
}
