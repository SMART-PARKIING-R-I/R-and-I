package com.example.smartparking

import android.graphics.Paint
import android.graphics.Typeface
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.res.imageResource
import androidx.compose.ui.unit.IntSize
import kotlin.math.max
import kotlin.math.min

val FreeGreen = Color(0xFF16A34A)
val BusyRed = Color(0xFFDC2626)
val RouteBlue = Color(0xFF2563EB)

/**
 * Bird's-eye photo of the lot. Every bay is tinted green (free) or red (occupied) from the live
 * camera data. With an [assignment] it also draws the animated route and the destination bay.
 * [zoom] = true fits the view to the route; false shows the whole lot.
 */
@Composable
fun LotMapView(
    map: LotMap,
    freeIds: Set<String>,
    assignment: Assignment?,
    zoom: Boolean,
    modifier: Modifier = Modifier,
) {
    val img = ImageBitmap.imageResource(R.drawable.lot_a)
    val phase by rememberInfiniteTransition(label = "dash").animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1100, easing = LinearEasing), RepeatMode.Restart),
        label = "phase",
    )
    val fill = remember {
        Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.WHITE
            textAlign = Paint.Align.CENTER
            typeface = Typeface.DEFAULT_BOLD
        }
    }
    val outline = remember {
        Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.BLACK
            textAlign = Paint.Align.CENTER
            typeface = Typeface.DEFAULT_BOLD
            style = Paint.Style.STROKE
            strokeJoin = Paint.Join.ROUND
        }
    }
    val dest = remember(map, assignment) { assignment?.let { a -> map.bays.first { it.spotId == a.spotId } } }

    Canvas(modifier.fillMaxSize().background(Color(0xFFCBD5E1))) {
        val W = map.width.toFloat()
        val H = map.height.toFloat()
        val ar = size.width / size.height
        var x = 0f; var y = 0f; var w = W; var h = H
        val fitRoute = zoom && assignment != null && dest != null
        if (fitRoute) {
            val pts = assignment!!.route + dest!!.polygon
            val pad = 95f
            x = pts.minOf { it.x } - pad
            y = pts.minOf { it.y } - pad
            w = pts.maxOf { it.x } + pad - x
            h = pts.maxOf { it.y } + pad - y
        }
        if (w / h < ar) { val nw = h * ar; x -= (nw - w) / 2; w = nw }
        else { val nh = w / ar; y -= (nh - h) / 2; h = nh }
        if (fitRoute) {
            x = x.coerceIn(0f, max(0f, W - w))
            y = y.coerceIn(0f, max(0f, H - h))
        }
        val k = w / size.width              // photo units per screen pixel

        withTransform({ scale(1f / k, 1f / k, Offset.Zero); translate(-x, -y) }) {
            drawImage(img, dstSize = IntSize(map.width, map.height))

            fun label(t: String, cx: Float, cy: Float, textSize: Float, withOutline: Boolean = true) {
                fill.textSize = textSize
                outline.textSize = textSize
                outline.strokeWidth = textSize * 0.28f
                val dy = -(fill.ascent() + fill.descent()) / 2
                val c = drawContext.canvas.nativeCanvas
                if (withOutline) c.drawText(t, cx, cy + dy, outline)
                c.drawText(t, cx, cy + dy, fill)
            }

            // occupancy: green = free, red = occupied
            for (b in map.bays) {
                val free = b.spotId in freeIds
                val poly = Path().apply {
                    moveTo(b.polygon[0].x, b.polygon[0].y)
                    for (p in b.polygon.drop(1)) lineTo(p.x, p.y)
                    close()
                }
                drawPath(poly, (if (free) FreeGreen else BusyRed).copy(alpha = if (free) 0.42f else 0.55f))
                drawPath(poly, Color.White.copy(alpha = 0.85f), style = Stroke(1.2f * k))
            }
            for (b in map.bays) {
                if (b.spotId == assignment?.spotId) continue
                val cx = (b.polygon.minOf { it.x } + b.polygon.maxOf { it.x }) / 2
                val cy = (b.polygon.minOf { it.y } + b.polygon.maxOf { it.y }) / 2
                label(b.number.toString(), cx, cy, (if (fitRoute) 13f else 10f) * k)
            }

            if (assignment != null && dest != null) {
                val r = assignment.route
                val path = Path().apply {
                    moveTo(r[0].x, r[0].y)
                    for (p in r.drop(1)) lineTo(p.x, p.y)
                }
                drawPath(path, Color.White, style = Stroke(10f * k, cap = StrokeCap.Round, join = StrokeJoin.Round))
                drawPath(path, RouteBlue, style = Stroke(
                    6.5f * k, cap = StrokeCap.Round, join = StrokeJoin.Round,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(16f * k, 11f * k), phase * 27f * k),
                ))

                val e = map.entrance
                drawCircle(Color.White, 15f * k, e)
                drawCircle(RouteBlue, 10f * k, e)
                label("You are here", e.x - 66f * k, e.y + 28f * k, 14f * k)

                // destination bay drawn last so nothing covers its number
                val minX = dest.polygon.minOf { it.x }; val maxX = dest.polygon.maxOf { it.x }
                val minY = dest.polygon.minOf { it.y }; val maxY = dest.polygon.maxOf { it.y }
                val bw = (maxX - minX) * 0.82f
                val bh = (maxY - minY) * 0.92f
                val cx = (minX + maxX) / 2
                val cy = (minY + maxY) / 2
                val tl = Offset(cx - bw / 2, cy - bh / 2)
                drawRoundRect(FreeGreen, tl, Size(bw, bh), CornerRadius(6f * k))
                drawRoundRect(Color.White, tl, Size(bw, bh), CornerRadius(6f * k), style = Stroke(3f * k))
                label(assignment.number.toString(), cx, cy, min(bw * 0.8f, 24f * k), withOutline = false)
            }
        }
    }
}
