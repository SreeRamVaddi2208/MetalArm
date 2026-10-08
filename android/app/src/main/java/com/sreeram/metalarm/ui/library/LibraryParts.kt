// What the Library screens share - the twin of iOS LibraryParts.swift:
// program cards, workout rows, path chips and the schedule grid.

package com.sreeram.metalarm.ui.library

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sreeram.metalarm.api.LibraryProgramCard
import com.sreeram.metalarm.api.LibraryVocabulary
import com.sreeram.metalarm.api.LibraryWorkoutCard
import com.sreeram.metalarm.api.ScheduleWeek
import com.sreeram.metalarm.theme.Chip
import com.sreeram.metalarm.theme.ChipRow
import com.sreeram.metalarm.theme.ListRow
import com.sreeram.metalarm.theme.Pill
import com.sreeram.metalarm.theme.Theme
import com.sreeram.metalarm.theme.bleed
import com.sreeram.metalarm.theme.card

/** Name, one line of description, weeks · days · level. A program for the
 *  user's path carries a quiet "For your path" pill. */
@Composable
fun ProgramCard(program: LibraryProgramCard, onOpen: () -> Unit, modifier: Modifier = Modifier, showPill: Boolean = true) {
    val pill = showPill && program.recommended
    Column(
        modifier
            .card()
            .clickable(role = Role.Button, onClick = onOpen)
            .testTag("library-program-${program.slug}"),
        verticalArrangement = Arrangement.spacedBy(Theme.Space.s8),
    ) {
        if (pill || program.following == true) {
            Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
                if (pill) Pill("For your path")
                if (program.following == true) Pill("Following", accent = false)
            }
        }
        Text(program.name, style = Theme.title, color = Theme.text, maxLines = 2, overflow = TextOverflow.Ellipsis)
        program.description?.takeIf { it.isNotEmpty() }?.let {
            Text(it, style = Theme.body, color = Theme.text2, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Text(program.meta, style = Theme.caption, color = Theme.text2)
    }
}

/** A list row: name, then duration · exercises · equipment. */
@Composable
fun WorkoutRow(workout: LibraryWorkoutCard, onOpen: () -> Unit) {
    ListRow(
        workout.name, Modifier.testTag("library-workout-${workout.slug}"),
        subtitle = "${workout.meta} · ${workout.gear}", chevron = true, onClick = onOpen,
    )
}

/** The three paths; the user's own is marked with a dot. */
@Composable
fun PathChips(selected: String, own: String, onSelect: (String) -> Unit) {
    ChipRow {
        LibraryVocabulary.paths.forEach { (category, label) ->
            Chip(label, { onSelect(category) }, Modifier.testTag("path-chip-$category"), selected = category == selected, dot = category == own)
        }
    }
}

/** Weeks as rows, days 1-7 as cells. A workout day shows its name and opens
 *  it; a rest day is a muted outline. Scrolls sideways in its own row. */
@Composable
fun ScheduleGrid(weeks: List<ScheduleWeek>, onOpenWorkout: (String) -> Unit) {
    val cell = 76.dp
    val weekColumn = 40.dp
    val shape = RoundedCornerShape(Theme.radius)
    Column(
        Modifier
            .bleed()
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = Theme.gutter)
            .semantics { contentDescription = "Program schedule" }
            .testTag("programSchedule"),
        verticalArrangement = Arrangement.spacedBy(Theme.Space.s4),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
            Spacer(Modifier.width(weekColumn))
            (1..7).forEach { Text("Day $it", style = Theme.caption, color = Theme.text2, textAlign = TextAlign.Center, modifier = Modifier.width(cell)) }
        }
        weeks.forEach { week ->
            Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s4), verticalAlignment = Alignment.CenterVertically) {
                Text("W${week.week}", style = Theme.caption, color = Theme.text2, textAlign = TextAlign.Center, modifier = Modifier.width(weekColumn))
                week.days.forEach { day ->
                    val slug = day.workoutSlug
                    Box(
                        Modifier
                            .width(cell)
                            .height(Theme.touch)
                            .then(
                                if (slug != null) Modifier.background(Theme.surface2, shape).clickable(role = Role.Button) { onOpenWorkout(slug) }
                                else Modifier.border(BorderStroke(1.dp, Theme.border), shape),
                            )
                            .semantics(mergeDescendants = true) {
                                contentDescription = "Week ${week.week}, day ${day.day}: ${day.workoutName ?: "rest"}"
                            }
                            .padding(horizontal = Theme.Space.s4),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            day.workoutName ?: "Rest", style = Theme.caption, color = if (slug != null) Theme.text else Theme.text3,
                            textAlign = TextAlign.Center, maxLines = 2, overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
    }
}
