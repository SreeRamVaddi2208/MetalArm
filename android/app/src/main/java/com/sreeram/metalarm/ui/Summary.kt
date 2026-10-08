// The workout summary and the level-up / rank-up celebration - the twins of
// iOS SummaryView and LevelUpView. The summary: three stats, the record if
// there was one, every point and where it came from, Done pinned low. A level
// or rank gained opens with the celebration over it.

package com.sreeram.metalarm.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.sreeram.metalarm.api.FinishResult
import com.sreeram.metalarm.api.ProgressionDelta
import com.sreeram.metalarm.api.RankTitle
import com.sreeram.metalarm.api.WeightUnit
import com.sreeram.metalarm.api.celebrated
import com.sreeram.metalarm.api.formatNumber
import com.sreeram.metalarm.theme.ButtonKind
import com.sreeram.metalarm.theme.IconButton
import com.sreeram.metalarm.theme.ListRow
import com.sreeram.metalarm.theme.MAButton
import com.sreeram.metalarm.theme.Pill
import com.sreeram.metalarm.theme.RowGroup
import com.sreeram.metalarm.theme.Screen
import com.sreeram.metalarm.theme.SectionBlock
import com.sreeram.metalarm.theme.StatTile
import com.sreeram.metalarm.theme.Theme
import com.sreeram.metalarm.theme.rememberReduceMotion
import kotlin.math.cos
import kotlin.math.roundToLong
import kotlin.math.sin

@Composable
fun SummaryScreen(result: FinishResult, unit: WeightUnit, inviteCode: String?, onDone: () -> Unit) {
    val context = LocalContext.current
    var showingLevelUp by remember { mutableStateOf(result.progression.leveledUp || result.progression.rankedUp) }
    val lead = result.prEvents.celebrated
    val card = remember(result) { ShareCardContent.make(result, unit, inviteCode) }
    BackHandler(onBack = onDone)

    Box(Modifier.fillMaxSize().testTag("summaryScreen")) {
        Screen(
            modifier = Modifier.windowInsetsPadding(WindowInsets.navigationBars),
            pinned = { MAButton("Done", onDone, Modifier.testTag("doneButton")) },
        ) {
            Row(Modifier.padding(top = Theme.Space.s16), verticalAlignment = Alignment.CenterVertically) {
                Text(if (lead == null) "Workout complete" else "New personal record", style = Theme.titleLG, color = Theme.text, modifier = Modifier.weight(1f))
                IconButton(Icons.Filled.Share, "Share", { ShareCardRenderer.share(context, card) }, Modifier.testTag("shareButton"))
            }
            if (lead != null) {
                Column(
                    Modifier.fillMaxWidth().background(Theme.accentSoft, RoundedCornerShape(Theme.radius)).padding(Theme.Space.s12),
                    verticalArrangement = Arrangement.spacedBy(Theme.Space.s4),
                ) {
                    Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s8), verticalAlignment = Alignment.CenterVertically) {
                        Pill("PR")
                        Text(lead.headline(unit), style = Theme.body, color = Theme.text)
                    }
                    Text(lead.motivation, style = Theme.caption, color = Theme.text2, modifier = Modifier.testTag("prMotivation"))
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
                StatTile("${maxOf(1, result.session.durationSeconds / 60)}", "Duration", Modifier.weight(1f), unit = "min")
                StatTile(formatNumber(unit.fromKilograms(result.session.totalVolumeKg).roundToLong().toDouble()), "Volume", Modifier.weight(1f), unit = unit.raw)
                StatTile("${result.session.workingSets}", "Sets", Modifier.weight(1f))
            }
            if (!result.qualified) {
                Text(
                    "Short workout: under 10 minutes or fewer than 3 working sets, so no completion bonus or streak credit. Your set points still count.",
                    style = Theme.caption, color = Theme.text2, modifier = Modifier.testTag("unqualifiedNote"),
                )
            }
            SectionBlock("Points") {
                val b = result.breakdown
                RowGroup {
                    row { BreakdownRow("Sets logged", b.setPoints) }
                    row { BreakdownRow("Workout completed", b.sessionBonus) }
                    row { BreakdownRow("PR bonus", b.prBonus) }
                    row { BreakdownRow("Streak bonus", b.streakBonus) }
                    if (b.reversals != 0) row { BreakdownRow("Adjustments", b.reversals) }
                }
                Row(verticalAlignment = Alignment.Bottom) {
                    Text("Total", style = Theme.body, color = Theme.text2, modifier = Modifier.weight(1f))
                    Text("+${b.total}", style = Theme.display, color = Theme.accent, modifier = Modifier.testTag("pointsTotal"))
                }
                if (result.progression.hint.isNotEmpty()) Text(result.progression.hint, style = Theme.caption, color = Theme.text2)
            }
            Text(
                "${result.streak.weeks}-week streak · ${result.streak.thisWeekSessions}/${result.streak.target} workouts this week",
                style = Theme.caption, color = Theme.text2,
            )
        }
        if (showingLevelUp) {
            LevelUpOverlay(result.progression, onShare = { ShareCardRenderer.share(context, card) }) { showingLevelUp = false }
        }
    }
}

@Composable
private fun BreakdownRow(label: String, points: Int) = ListRow(label, trailing = if (points >= 0) "+$points" else "$points")

/** The reward moment: the new level (or rank) lands, rings and sparks fly
 *  out, then the words. Tier colour on a rank-up, the accent on a level-up -
 *  the one place a glow is allowed. Tapping anywhere continues. */
@Composable
fun LevelUpOverlay(progression: ProgressionDelta, onShare: () -> Unit, onContinue: () -> Unit) {
    val still = rememberReduceMotion()
    val haptics = LocalHapticFeedback.current
    val isRankUp = progression.rankedUp
    val glow = if (isRankUp) Theme.tier(progression.rankAfter) else Theme.accent
    val gained = maxOf(1, progression.levelAfter - progression.levelBefore)
    val badge = if (isRankUp) RankTitle.of(progression.rankAfter) else "${progression.levelAfter}"
    val subtitle = when {
        isRankUp -> "You're now ${RankTitle.of(progression.rankAfter)} at level ${progression.levelAfter}."
        gained > 1 -> "+$gained levels. You reached level ${progression.levelAfter}."
        else -> "You reached level ${progression.levelAfter}. Keep going."
    }
    var appeared by remember { mutableStateOf(false) }
    val shown by animateFloatAsState(if (appeared) 1f else 0f, tween(if (still) 250 else 450), label = "shown")
    val burst by animateFloatAsState(if (appeared && !still) 1f else 0f, tween(1100), label = "burst")
    val landing by animateFloatAsState(if (appeared || still) 1f else if (isRankUp) 1.25f else 0.4f, tween(if (still) 0 else 600), label = "landing")
    LaunchedEffect(Unit) {
        appeared = true
        haptics.performHapticFeedback(HapticFeedbackType.LongPress)
        if (isRankUp) {
            kotlinx.coroutines.delay(200)
            haptics.performHapticFeedback(HapticFeedbackType.LongPress)
        }
    }
    BackHandler(onBack = onContinue)

    Box(
        Modifier
            .fillMaxSize()
            .background(Theme.bg.copy(alpha = 0.96f))
            .clickable(remember { MutableInteractionSource() }, indication = null, onClick = onContinue)
            .semantics {
                liveRegion = LiveRegionMode.Assertive
                contentDescription = if (isRankUp) "Rank up. You are now ${RankTitle.of(progression.rankAfter)}."
                else "Level up. You reached level ${progression.levelAfter}."
            }
            .testTag("levelUpOverlay"),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.fillMaxSize().alpha(shown)) {
            drawRect(Brush.radialGradient(listOf(glow.copy(alpha = if (isRankUp) 0.3f else 0.2f), Color.Transparent), radius = 380.dp.toPx()))
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(Theme.Space.s16),
            modifier = Modifier.padding(horizontal = Theme.Space.s24)) {
            Box(Modifier.fillMaxWidth().height(230.dp), contentAlignment = Alignment.Center) {
                if (!still) {
                    Canvas(Modifier.fillMaxSize()) {
                        val centre = center
                        repeat(if (isRankUp) 5 else 3) { ring ->
                            val scale = 0.6f + burst * (1.5f + ring * 0.35f)
                            drawCircle(glow.copy(alpha = 0.9f * (1 - burst)), radius = 75.dp.toPx() * scale, center = centre, style = Stroke(3.dp.toPx()))
                        }
                        repeat(24) { index ->
                            val angle = index / 24.0 * 2 * Math.PI
                            val distance = ((if (isRankUp) 185 else 150) + (index * 37) % 70).dp.toPx() * burst
                            val at = Offset(centre.x + (cos(angle) * distance).toFloat(), centre.y + (sin(angle) * distance).toFloat())
                            drawCircle(if (index % 3 == 0) glow.copy(alpha = 1 - burst) else Theme.text2.copy(alpha = 1 - burst), radius = 2.dp.toPx(), center = at)
                        }
                    }
                }
                Text(badge, style = Theme.hero(if (isRankUp) 54 else 120), color = glow, maxLines = 1,
                    modifier = Modifier.scale(landing).alpha(shown))
            }
            if (isRankUp) {
                Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s8), verticalAlignment = Alignment.CenterVertically, modifier = Modifier.alpha(shown)) {
                    Text(RankTitle.of(progression.rankBefore), style = Theme.label, color = Theme.text3)
                    Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null, tint = Theme.text2)
                    Text(RankTitle.of(progression.rankAfter), style = Theme.label, color = Theme.text)
                }
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(Theme.Space.s8), modifier = Modifier.alpha(shown)) {
                Text(if (isRankUp) "Rank up" else "Level up", style = Theme.titleLG, color = Theme.text)
                Text(subtitle, style = Theme.body, color = Theme.text2, textAlign = TextAlign.Center)
            }
            MAButton("Continue", onContinue, Modifier.padding(horizontal = Theme.Space.s32).padding(top = Theme.Space.s16).alpha(shown).testTag("levelUpContinueButton"))
            MAButton("Share", onShare, Modifier.alpha(shown).testTag("levelUpShareButton"), kind = ButtonKind.Ghost, icon = Icons.Filled.Share)
        }
    }
}
