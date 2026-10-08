// Progress - the twin of iOS ProgressScreen: an exercise's top set over time
// as one accent line (a dot on the latest point), and its records.

package com.sreeram.metalarm.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ShowChart
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.sreeram.metalarm.api.WorkoutRecord
import com.sreeram.metalarm.api.formatNumber
import com.sreeram.metalarm.api.parseServerDate
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.Chip
import com.sreeram.metalarm.theme.ChipRow
import com.sreeram.metalarm.theme.EmptyState
import com.sreeram.metalarm.theme.ErrorState
import com.sreeram.metalarm.theme.ListRow
import com.sreeram.metalarm.theme.RowGroup
import com.sreeram.metalarm.theme.Screen
import com.sreeram.metalarm.theme.ScreenTitle
import com.sreeram.metalarm.theme.SectionBlock
import com.sreeram.metalarm.theme.Theme
import kotlinx.coroutines.launch
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.abs

private val shortDate = DateTimeFormatter.ofPattern("MMM d", Locale.US).withZone(ZoneId.systemDefault())
private val longDate = DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US).withZone(ZoneId.systemDefault())

@Composable
fun ProgressScreen(model: AppModel) {
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) { model.loadProgress() }
    Screen {
        ScreenTitle("Progress")
        if (model.progressTabs.isEmpty()) {
            if (!model.isBusy) EmptyState(Icons.AutoMirrored.Outlined.ShowChart, "Finish a workout to start tracking your progress.")
        } else {
            ChipRow {
                model.progressTabs.forEach { tab ->
                    Chip(tab.name, { scope.launch { model.selectProgress(tab.id) } }, Modifier.testTag("progressTab-${tab.name}"),
                        selected = tab.id == model.selectedProgressId)
                }
            }
            Chart(model)
            SectionBlock("Records") {
                if (model.records.isEmpty() && !model.isBusy) {
                    Text("Records appear as you beat your best on this exercise.", style = Theme.body, color = Theme.text2)
                } else {
                    RowGroup {
                        sorted(model.records).forEach { record ->
                            row {
                                ListRow(
                                    "${record.label} — ${record.exerciseName}",
                                    Modifier.testTag("record-${record.label} — ${record.exerciseName}"),
                                    subtitle = parseServerDate(record.achievedAt)?.let(longDate::format) ?: record.achievedAt.take(10),
                                    trailing = record.valueText(model.weightUnit),
                                )
                            }
                        }
                    }
                }
            }
        }
        ErrorState(model.errorMessage)
    }
}

/** One row per record type; "most reps" has one per weight, so the heaviest three. */
private fun sorted(records: List<WorkoutRecord>): List<WorkoutRecord> {
    val order = WorkoutRecord.displayOrder
    val others = records.filter { it.recordType != "max_reps_at_weight" }
        .sortedBy { order.indexOf(it.recordType).let { i -> if (i < 0) order.size else i } }
    val reps = records.filter { it.recordType == "max_reps_at_weight" }.sortedByDescending { it.weightKg ?: 0.0 }.take(3)
    return others + reps
}

@Composable
private fun Chart(model: AppModel) {
    val unit = model.weightUnit
    val points = model.history.mapNotNull { point ->
        val top = point.topWeightKg ?: return@mapNotNull null
        val date = parseServerDate(point.performedAt) ?: return@mapNotNull null
        date to unit.fromKilograms(top)
    }
    val first = points.firstOrNull()
    val last = points.lastOrNull()
    if (first == null || last == null) {
        EmptyState(Icons.AutoMirrored.Outlined.ShowChart, "No finished workouts with this exercise yet.")
        return
    }
    Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
        Text("Top set", style = Theme.caption, color = Theme.text2)
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
            Text(formatNumber(last.second), style = Theme.display, color = Theme.text)
            Text(unit.raw, style = Theme.caption, color = Theme.text2, modifier = Modifier.testTag("topSetUnit"))
        }
        if (points.size > 1) {
            val change = last.second - first.second
            Text(
                "${if (change >= 0) "+" else "−"}${formatNumber(abs(change))} ${unit.raw} since ${shortDate.format(first.first)}",
                style = Theme.caption, color = Theme.text2,
            )
        }
        val values = points.map { it.second }
        val low = values.min()
        val high = values.max()
        Row(verticalAlignment = Alignment.Top) {
        Canvas(
            Modifier.weight(1f).height(200.dp).semantics {
                contentDescription = "Top set over time, from ${formatNumber(first.second)} to ${formatNumber(last.second)} ${unit.raw}"
            },
        ) {
            val span = (high - low).takeIf { it > 0 } ?: 1.0
            val inset = 8.dp.toPx()
            fun at(index: Int, value: Double) = Offset(
                inset + (size.width - 2 * inset) * (if (points.size == 1) 0.5f else index / (points.size - 1f)),
                inset + (size.height - 2 * inset) * (1 - ((value - low) / span).toFloat()),
            )
            // Three quiet grid lines.
            repeat(3) { line ->
                val y = inset + (size.height - 2 * inset) * line / 2f
                drawLine(Theme.border, Offset(0f, y), Offset(size.width, y), strokeWidth = 1.dp.toPx())
            }
            val path = Path()
            points.forEachIndexed { index, (_, value) ->
                val p = at(index, value)
                if (index == 0) path.moveTo(p.x, p.y) else path.lineTo(p.x, p.y)
            }
            drawPath(path, Theme.accent, style = Stroke(2.5.dp.toPx(), cap = StrokeCap.Round))
            drawCircle(Theme.accent, radius = 5.dp.toPx(), center = at(points.size - 1, last.second))
        }
            // The values the three grid lines stand for, on the trailing edge.
            Column(
                Modifier.height(200.dp).padding(start = Theme.Space.s8),
                verticalArrangement = Arrangement.SpaceBetween,
            ) {
                listOf(high, (high + low) / 2, low).forEach {
                    Text(formatNumber(Math.round(it * 10) / 10.0), style = Theme.caption, color = Theme.text2)
                }
            }
        }
        // First, middle and last dates under the line.
        Row(Modifier.fillMaxWidth()) {
            val dates = listOf(points.first().first, points[points.size / 2].first, points.last().first).distinct()
            dates.forEachIndexed { index, date ->
                if (index > 0) androidx.compose.foundation.layout.Spacer(Modifier.weight(1f))
                Text(shortDate.format(date), style = Theme.caption, color = Theme.text2)
            }
            androidx.compose.foundation.layout.Spacer(Modifier.width(Theme.Space.s32))
        }
    }
}
