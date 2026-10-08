// The story card shared from the summary and the celebration - the twin of
// iOS ShareCard.swift. The biggest moment of the workout leads: rank-up, then
// level-up, then a record, else the points. Drawn straight to a 1080 x 1920
// bitmap (the stories size); its type is sized for the image, outside the
// app's scale.

package com.sreeram.metalarm.ui

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import androidx.compose.ui.graphics.toArgb
import androidx.core.content.FileProvider
import androidx.core.content.res.ResourcesCompat
import com.sreeram.metalarm.R
import com.sreeram.metalarm.api.FinishResult
import com.sreeram.metalarm.api.RankTitle
import com.sreeram.metalarm.api.WeightUnit
import com.sreeram.metalarm.api.celebrated
import com.sreeram.metalarm.api.formatNumber
import com.sreeram.metalarm.theme.Theme
import java.io.File
import kotlin.math.roundToLong

data class ShareCardContent(
    val kind: Kind,
    val eyebrow: String,
    val headline: String,
    val caption: String,
    /** The line that follows a personal record; empty for the other kinds. */
    val note: String = "",
    val stats: List<Pair<String, String>>,
    val inviteCode: String?,
) {
    enum class Kind { RankUp, LevelUp, Record, Workout }

    companion object {
        fun make(result: FinishResult, unit: WeightUnit, inviteCode: String?): ShareCardContent {
            val progression = result.progression
            val volume = formatNumber(unit.fromKilograms(result.session.totalVolumeKg).roundToLong().toDouble())
            val sets = result.session.workingSets
            val stats = listOf(
                "${maxOf(1, result.session.durationSeconds / 60)} min" to "Duration",
                "$volume ${unit.raw}" to "Volume",
                "$sets" to if (sets == 1) "Set" else "Sets",
            )
            val code = inviteCode?.takeIf { it.isNotEmpty() }
            if (progression.rankedUp) {
                return ShareCardContent(Kind.RankUp, "RANK UP", RankTitle.of(progression.rankAfter).uppercase(),
                    "${RankTitle.of(progression.rankAfter)} at level ${progression.levelAfter}", stats = stats, inviteCode = code)
            }
            if (progression.leveledUp) {
                return ShareCardContent(Kind.LevelUp, "LEVEL UP", "${progression.levelAfter}",
                    "Level ${progression.levelAfter} reached", stats = stats, inviteCode = code)
            }
            result.prEvents.celebrated?.let { record ->
                return ShareCardContent(Kind.Record, "NEW PERSONAL RECORD", "PR", record.headline(unit),
                    note = record.motivation, stats = stats, inviteCode = code)
            }
            return ShareCardContent(Kind.Workout, "WORKOUT COMPLETE", "+${result.breakdown.total}", "points earned",
                stats = stats, inviteCode = code)
        }
    }
}

object ShareCardRenderer {
    const val WIDTH = 1080
    const val HEIGHT = 1920

    fun render(context: Context, content: ShareCardContent): Bitmap {
        val bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val s = 3f // laid out at 360 x 640, drawn at 3x
        val display = ResourcesCompat.getFont(context, R.font.space_grotesk_bold) ?: Typeface.DEFAULT_BOLD
        val body = ResourcesCompat.getFont(context, R.font.manrope_regular) ?: Typeface.DEFAULT
        val semibold = ResourcesCompat.getFont(context, R.font.manrope_semi_bold) ?: Typeface.DEFAULT_BOLD

        canvas.drawColor(Theme.bg.toArgb())
        val glow = Paint().apply {
            shader = RadialGradient(WIDTH / 2f, HEIGHT * 0.4f, 300 * s, Theme.text2.copy(alpha = 0.28f).toArgb(), 0, Shader.TileMode.CLAMP)
        }
        canvas.drawRect(0f, 0f, WIDTH.toFloat(), HEIGHT.toFloat(), glow)

        fun paint(face: Typeface, size: Float, color: Int, spacing: Float = 0f) = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            typeface = face
            textSize = size * s
            this.color = color
            letterSpacing = spacing
            textAlign = Paint.Align.CENTER
        }

        fun centered(text: String, paint: TextPaint, y: Float) = canvas.drawText(text, WIDTH / 2f, y, paint)

        fun wrapped(text: String, paint: TextPaint, top: Float): Float {
            val left = TextPaint(paint).apply { textAlign = Paint.Align.LEFT }
            val layout = StaticLayout.Builder.obtain(text, 0, text.length, left, (WIDTH - 64 * s).toInt())
                .setAlignment(Layout.Alignment.ALIGN_CENTER).build()
            canvas.save()
            canvas.translate(32 * s, top)
            layout.draw(canvas)
            canvas.restore()
            return top + layout.height
        }

        centered("METALARM", paint(display, 14f, Theme.text2.toArgb(), 0.4f), 70 * s)

        var y = 250 * s
        centered(content.eyebrow, paint(display, 16f, Theme.text2.toArgb(), 0.3f), y)
        val headline = paint(display, 120f, Theme.accent.toArgb())
        while (headline.measureText(content.headline) > WIDTH - 48 * s && headline.textSize > 40 * s) headline.textSize -= 4 * s
        headline.setShadowLayer(18 * s, 0f, 0f, Theme.accent.copy(alpha = 0.35f).toArgb())
        y += headline.textSize * 0.95f
        centered(content.headline, headline, y)
        y = wrapped(content.caption, paint(body, 15f, Theme.text.toArgb()), y + 16 * s)
        if (content.note.isNotEmpty()) wrapped(content.note, paint(semibold, 13f, Theme.text2.toArgb()), y + 8 * s)

        // The three stats, in surface boxes.
        val boxTop = 640 * s - 48 * s - 18 * s - 13 * s - 64 * s
        val gap = 10 * s
        val boxWidth = (WIDTH - 48 * s - 2 * gap) / 3
        val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Theme.surface.toArgb() }
        val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Theme.border.toArgb(); style = Paint.Style.STROKE; strokeWidth = s }
        content.stats.forEachIndexed { index, (value, label) ->
            val left = 24 * s + index * (boxWidth + gap)
            val rect = RectF(left, boxTop, left + boxWidth, boxTop + 58 * s)
            canvas.drawRoundRect(rect, 12 * s, 12 * s, fill)
            canvas.drawRoundRect(rect, 12 * s, 12 * s, stroke)
            canvas.drawText(value, rect.centerX(), rect.top + 28 * s, paint(display, 16f, Theme.text.toArgb()))
            canvas.drawText(label, rect.centerX(), rect.top + 45 * s, paint(body, 10f, Theme.text2.toArgb()))
        }
        centered(content.inviteCode?.let { "Join my party: $it" } ?: "Level up every workout",
            paint(semibold, 13f, Theme.text2.toArgb()), HEIGHT - 48 * s)
        return bitmap
    }

    /** Saves the card and opens the share sheet. */
    fun share(context: Context, content: ShareCardContent) {
        val dir = File(context.cacheDir, "share").apply { mkdirs() }
        val file = File(dir, "metalarm-workout.png")
        file.outputStream().use { render(context, content).compress(Bitmap.CompressFormat.PNG, 100, it) }
        val uri = FileProvider.getUriForFile(context, context.packageName + ".files", file)
        val send = Intent(Intent.ACTION_SEND).setType("image/png").putExtra(Intent.EXTRA_STREAM, uri)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        context.startActivity(Intent.createChooser(send, "Share your workout"))
    }
}
