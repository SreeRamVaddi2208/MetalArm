// Design tokens: the minimal design system, the same values as the web app's
// frontend/metalarm/theme.py and the iOS app's Theme/Theme.swift (see
// frontend/DESIGN_SYSTEM.md). Near-black neutrals and ONE accent, Forge
// orange; danger red for destructive actions only; rank-tier colours only
// inside RankBadge and the rank-up overlay.
//
// Screens use these tokens and the primitives in Components.kt - never a raw
// colour, size or radius (scripts/check_client_tokens.py enforces it).

package com.sreeram.metalarm.theme

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sreeram.metalarm.R

object Theme {
    // Colour

    val bg = Color(0xFF0E0E10)
    val surface = Color(0xFF17171A)
    val surface2 = Color(0xFF202024)
    /** 1 dp hairlines and input outlines only. */
    val border = Color(0xFF2A2A2F)
    val text = Color(0xFFF4F4F2)
    val text2 = Color(0xFFA1A1A8)
    /** Placeholders, "last time" ghosts, disabled. */
    val text3 = Color(0xFF6E6E76)
    /** The one accent: the primary button, the active tab, progress fills,
     *  the PR highlight, selected chips. */
    val accent = Color(0xFFFF6B2C)
    val accentSoft = accent.copy(alpha = 0.14f)
    val onAccent = Color(0xFF0E0E10)
    val danger = Color(0xFFE5484D)
    val scrim = Color(0xFF000000).copy(alpha = 0.6f)

    /** Rank tiers, E to S. Read only by RankBadge and LevelUpOverlay. */
    val tierColors: Map<String, Color> = mapOf(
        "E" to Color(0xFF8A6B4E), "D" to Color(0xFF9AA4AE), "C" to Color(0xFFD4A93C),
        "B" to Color(0xFF3FB6B0), "A" to Color(0xFF5BA8FF), "S" to Color(0xFFC77DFF),
    )

    fun tier(rank: String): Color = tierColors[rank.uppercase()] ?: text2

    // Type: Space Grotesk for titles and numbers, Manrope for the rest
    // (res/font, SIL Open Font License - android/licenses). Sizes are sp, so
    // they follow the system font size. Tabular figures throughout.

    private val spaceGrotesk = FontFamily(
        Font(R.font.space_grotesk_regular, FontWeight.Normal),
        Font(R.font.space_grotesk_medium, FontWeight.Medium),
        Font(R.font.space_grotesk_semi_bold, FontWeight.SemiBold),
        Font(R.font.space_grotesk_bold, FontWeight.Bold),
    )
    private val manrope = FontFamily(
        Font(R.font.manrope_regular, FontWeight.Normal),
        Font(R.font.manrope_medium, FontWeight.Medium),
        Font(R.font.manrope_semi_bold, FontWeight.SemiBold),
        Font(R.font.manrope_bold, FontWeight.Bold),
    )
    private const val TABULAR = "tnum"

    /** The hero number: the timer, the set being entered, the points total. */
    val display = TextStyle(fontFamily = spaceGrotesk, fontWeight = FontWeight.SemiBold, fontSize = 48.sp,
        lineHeight = 52.sp, fontFeatureSettings = TABULAR)
    /** A screen's title. */
    val titleLG = TextStyle(fontFamily = spaceGrotesk, fontWeight = FontWeight.SemiBold, fontSize = 28.sp,
        lineHeight = 34.sp, fontFeatureSettings = TABULAR)
    /** Section and card titles. */
    val title = TextStyle(fontFamily = spaceGrotesk, fontWeight = FontWeight.SemiBold, fontSize = 20.sp,
        lineHeight = 26.sp, fontFeatureSettings = TABULAR)
    val body = TextStyle(fontFamily = manrope, fontWeight = FontWeight.Medium, fontSize = 16.sp,
        lineHeight = 24.sp, fontFeatureSettings = TABULAR)
    /** Buttons and row labels. */
    val label = TextStyle(fontFamily = manrope, fontWeight = FontWeight.SemiBold, fontSize = 14.sp,
        lineHeight = 20.sp, fontFeatureSettings = TABULAR)
    /** Meta, units, timestamps. */
    val caption = TextStyle(fontFamily = manrope, fontWeight = FontWeight.Medium, fontSize = 12.sp,
        lineHeight = 16.sp, fontFeatureSettings = TABULAR)

    /** Reward moments only (the rank-up overlay): a size outside the scale. */
    fun hero(size: Int) = TextStyle(fontFamily = spaceGrotesk, fontWeight = FontWeight.Bold, fontSize = size.sp,
        lineHeight = (size * 1.1f).sp)

    // Space, size, shape, motion

    object Space {
        val s4 = 4.dp
        val s8 = 8.dp
        val s12 = 12.dp
        val s16 = 16.dp
        val s24 = 24.dp
        val s32 = 32.dp
        val s48 = 48.dp
    }

    /** Screen side padding. */
    val gutter = 20.dp
    val cardPadding = 16.dp
    /** Minimum tap target; an icon button is 44. */
    val touch = 48.dp
    val iconHit = 44.dp
    val rowMin = 56.dp
    val buttonHeight = 52.dp

    /** Cards and inputs. */
    val radius = 12.dp
    /** Sheets (top corners). */
    val radiusSheet = 16.dp

    const val FAST_MS = 150
    const val BASE_MS = 250
}
