// The Train tab - the twin of iOS WorkoutView. With nothing live: Start empty
// workout, and the way into the Library. With a workout live: one exercise in
// focus - its logged sets as calm rows, then weight and reps as steppers and
// Log set, the screen's one accent action, pinned low. Chips switch exercise;
// focus also moves on by itself once an exercise has done its plan.
//
// The session lives on the server, so leaving the tab (or the app) loses
// nothing: it is rehydrated from /workouts/sessions/active.

package com.sreeram.metalarm.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ListAlt
import androidx.compose.material.icons.automirrored.outlined.LibraryBooks
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.outlined.ArrowCircleUp
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.MilitaryTech
import androidx.compose.material.icons.outlined.Timer
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import com.sreeram.metalarm.api.Exercise
import com.sreeram.metalarm.api.WorkoutSession
import com.sreeram.metalarm.api.formatNumber
import com.sreeram.metalarm.api.plural
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.ButtonKind
import com.sreeram.metalarm.theme.Chip
import com.sreeram.metalarm.theme.ChipRow
import com.sreeram.metalarm.theme.EmptyState
import com.sreeram.metalarm.theme.ErrorState
import com.sreeram.metalarm.theme.IconButton
import com.sreeram.metalarm.theme.ListRow
import com.sreeram.metalarm.theme.MAButton
import com.sreeram.metalarm.theme.Pill
import com.sreeram.metalarm.theme.RowGroup
import com.sreeram.metalarm.theme.Screen
import com.sreeram.metalarm.theme.ScreenTitle
import com.sreeram.metalarm.theme.Theme
import com.sreeram.metalarm.theme.card
import kotlinx.coroutines.launch

@Composable
fun WorkoutScreen(model: AppModel, onOpenLibrary: () -> Unit) {
    var picking by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { model.loadWorkout() }

    val session = model.session
    if (session == null) EmptyWorkout(model, onOpenLibrary) else ActiveWorkout(model, session) { picking = true }
    if (picking) ExercisePicker(model) { picking = false }
}

@Composable
private fun EmptyWorkout(model: AppModel, onOpenLibrary: () -> Unit) {
    val scope = rememberCoroutineScope()
    Screen(
        pinned = {
            MAButton("Start empty workout", { scope.launch { model.startWorkout() } }, Modifier.testTag("workoutStartButton"), icon = Icons.Filled.PlayArrow)
        },
    ) {
        ScreenTitle("Train")
        Text(
            "Start a workout to log sets, earn points and chase records. Your last numbers fill in for you.",
            style = Theme.body, color = Theme.text2,
        )
        RowGroup {
            row {
                ListRow(
                    "Browse the Library", Modifier.testTag("trainToLibrary"),
                    subtitle = "Programs and ready-made workouts for your path", chevron = true, onClick = onOpenLibrary,
                ) { Icon(Icons.AutoMirrored.Outlined.LibraryBooks, contentDescription = null, tint = Theme.text2) }
            }
        }
        ErrorState(model.errorMessage)
    }
}

@Composable
private fun ActiveWorkout(model: AppModel, session: WorkoutSession, onAdd: () -> Unit) {
    val scope = rememberCoroutineScope()
    val focus = LocalFocusManager.current
    var confirmingDiscard by remember { mutableStateOf(false) }
    val exercise = model.selectedExercise

    Screen(
        pinned = if (exercise != null) {
            {
                MAButton(
                    "Log set",
                    {
                        focus.clearFocus()
                        scope.launch { model.logSet() }
                    },
                    Modifier.testTag("logSetButton"),
                    icon = Icons.Filled.Check, enabled = !model.isBusy,
                )
            }
        } else null,
    ) {
        Header(model, session, onDiscard = { confirmingDiscard = true }) {
            focus.clearFocus()
            scope.launch { model.finishWorkout() }
        }
        if (model.resting) Banner(Icons.Outlined.Timer, "Rest - ${model.restDisplay} until the next set", "restBanner", accent = true)
        if (model.pendingSets.isNotEmpty()) Banner(Icons.Outlined.CloudOff, model.syncStatusText, "offlineBanner")
        if (model.progressionHint.isNotEmpty()) Banner(Icons.Outlined.ArrowCircleUp, model.progressionHint, "progressionBanner")
        if (model.prHint.isNotEmpty()) Banner(Icons.Outlined.MilitaryTech, model.prHint, "prBanner", accent = true)
        ChipRow {
            model.workoutExercises.forEach { item ->
                Chip(item.name, { model.select(item.id) }, Modifier.testTag("chip-${item.name}"), selected = item.id == model.selectedExerciseId)
            }
            Chip("+ Add", onAdd, Modifier.testTag("addExerciseButton"))
        }
        if (exercise != null) {
            ExerciseCard(model, exercise)
        } else {
            EmptyState(Icons.AutoMirrored.Outlined.ListAlt, "Add the first exercise - your last session's numbers fill in for you.") {
                MAButton("Add exercise", onAdd, Modifier.testTag("addFirstExerciseButton"), kind = ButtonKind.Secondary, full = false)
            }
        }
        ErrorState(model.errorMessage)
    }

    if (confirmingDiscard) {
        AlertDialog(
            onDismissRequest = { confirmingDiscard = false },
            containerColor = Theme.surface,
            title = { Text("Discard this workout?", style = Theme.title, color = Theme.text) },
            text = { Text("Points from its sets are taken back.", style = Theme.body, color = Theme.text2) },
            confirmButton = {
                TextButton({
                    confirmingDiscard = false
                    scope.launch { model.abandonWorkout() }
                }, Modifier.testTag("confirmDiscardButton")) { Text("Discard workout", style = Theme.label, color = Theme.danger) }
            },
            dismissButton = { TextButton({ confirmingDiscard = false }) { Text("Cancel", style = Theme.label, color = Theme.text2) } },
        )
    }
}

@Composable
private fun Header(model: AppModel, session: WorkoutSession, onDiscard: () -> Unit, onFinish: () -> Unit) {
    var menu by remember { mutableStateOf(false) }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
        Column(Modifier.weight(1f)) {
            Text(session.name ?: "Workout", style = Theme.label, color = Theme.text, maxLines = 1)
            Text(
                "${plural(model.setsLoggedCount, "set")} · ${session.pointsTotal} pts",
                style = Theme.caption, color = Theme.text2, modifier = Modifier.testTag("setsLoggedText"),
            )
        }
        Box {
            IconButton(Icons.Filled.MoreHoriz, "Workout options", { menu = true }, Modifier.testTag("workoutOptions"))
            DropdownMenu(menu, { menu = false }, containerColor = Theme.surface2) {
                DropdownMenuItem(
                    { Text("Discard workout", style = Theme.body, color = Theme.danger) },
                    { menu = false; onDiscard() },
                    Modifier.testTag("discardWorkoutItem"),
                )
            }
        }
        MAButton("Finish", onFinish, Modifier.testTag("finishButton"), kind = ButtonKind.Ghost, enabled = !model.isBusy)
    }
}

@Composable
private fun ExerciseCard(model: AppModel, exercise: Exercise) {
    val unit = model.weightUnit
    val card = model.selectedSessionExercise
    val sets = card?.sets.orEmpty()
    val previous = model.selectedPreviousSets
    val queued = model.queuedSets(exercise.id)
    Column(Modifier.card(), verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
        Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
                Text(exercise.name, style = Theme.title, color = Theme.text)
                Text(
                    card?.supersetGroup?.let { "Superset $it · ${exercise.muscleLabel}" } ?: exercise.muscleLabel,
                    style = Theme.caption, color = Theme.text2,
                )
            }
            ExerciseDemo(exercise, Theme.touch, context = "cardExerciseDemo")
        }
        model.selectedHint?.let {
            Text(it.text, style = Theme.caption, color = Theme.text2, modifier = Modifier.testTag("progressionHint"))
        }
        if (sets.isNotEmpty() || queued.isNotEmpty()) {
            Column {
                sets.forEach { logged ->
                    DoneRow(
                        if (logged.isWarmup) "W" else "${logged.setNumber}",
                        "${formatNumber(unit.fromKilograms(logged.weightKg))} ${unit.raw} × ${logged.reps ?: 0}",
                        pr = logged.isPr,
                    )
                }
                // Saved offline: shown in place, with a clock until they sync.
                queued.forEachIndexed { offset, set ->
                    DoneRow(
                        "${sets.size + offset + 1}",
                        "${formatNumber(unit.fromKilograms(set.weightKg))} ${unit.raw} × ${set.reps}",
                        pending = true, tag = "queuedSet",
                    )
                }
            }
        }
        if (previous.isNotEmpty()) {
            Text(
                "Last time · " + previous.take(4).joinToString(", ") { "${formatNumber(unit.fromKilograms(it.weightKg))} × ${it.reps ?: 0}" },
                style = Theme.caption, color = Theme.text3, modifier = Modifier.testTag("ghostValues"),
            )
        }
        Text("Set ${sets.size + queued.size + 1}", style = Theme.label, color = Theme.text2)
        Stepper("Weight", unit.raw, model.weightInput, { model.weightInput = it }, KeyboardType.Decimal, "weight",
            minus = { model.bumpWeight(-1) }, plus = { model.bumpWeight(1) })
        Stepper("Reps", "reps", model.repsInput, { model.repsInput = it }, KeyboardType.Number, "reps",
            minus = { model.bumpReps(-1) }, plus = { model.bumpReps(1) })
    }
}

@Composable
private fun DoneRow(number: String, line: String, pr: Boolean = false, pending: Boolean = false, tag: String = "") {
    Row(
        Modifier.fillMaxWidth().heightIn(min = Theme.touch).then(if (tag.isNotEmpty()) Modifier.testTag(tag) else Modifier),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12),
    ) {
        Text(number, style = Theme.label, color = Theme.text2, modifier = Modifier.width(Theme.Space.s24))
        Text(line, style = Theme.body, color = Theme.text2, modifier = Modifier.weight(1f))
        if (pr) Pill("PR")
        Icon(
            if (pending) Icons.Outlined.History else Icons.Filled.Check,
            contentDescription = if (pending) "Waiting to sync" else "Logged",
            tint = if (pending) Theme.text3 else Theme.accent,
        )
    }
}

@Composable
private fun Stepper(
    label: String, unit: String, value: String, onChange: (String) -> Unit, keyboard: KeyboardType, tag: String,
    minus: () -> Unit, plus: () -> Unit,
) {
    Column(Modifier.testTag("${tag}Stepper"), verticalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
        Text(label, style = Theme.caption, color = Theme.text2)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
            StepButton(Icons.Filled.Remove, "Less ${label.lowercase()}", "${tag}Minus", minus)
            Row(Modifier.weight(1f), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.Bottom) {
                // Sized by the value (a hidden copy of it), so the unit sits
                // right beside the number.
                Box(contentAlignment = Alignment.Center) {
                    Text(value.ifEmpty { "0" }, style = Theme.display, color = Color.Transparent)
                    BasicTextField(
                        value = value,
                        onValueChange = onChange,
                        singleLine = true,
                        textStyle = Theme.display.copy(color = Theme.text),
                        cursorBrush = SolidColor(Theme.accent),
                        keyboardOptions = KeyboardOptions(keyboardType = keyboard),
                        modifier = Modifier.matchParentSize().testTag("${tag}Field"),
                        // Kept to the field's own size: unconstrained, the text
                        // layer grew to the row's width and drew off-field.
                        decorationBox = { inner ->
                            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                if (value.isEmpty()) Text("0", style = Theme.display, color = Theme.text3)
                                inner()
                            }
                        },
                    )
                }
                Text(unit, style = Theme.caption, color = Theme.text2)
            }
            StepButton(Icons.Filled.Add, "More ${label.lowercase()}", "${tag}Plus", plus)
        }
    }
}

@Composable
private fun StepButton(icon: ImageVector, label: String, tag: String, onClick: () -> Unit) {
    Box(
        Modifier
            .size(Theme.touch)
            .background(Theme.surface2, CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = label }
            .testTag(tag),
        contentAlignment = Alignment.Center,
    ) { Icon(icon, contentDescription = null, tint = Theme.text) }
}

@Composable
private fun Banner(icon: ImageVector, text: String, tag: String, accent: Boolean = false) {
    Row(
        Modifier.card(Theme.Space.s12).semantics(mergeDescendants = true) {}.testTag(tag),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12),
    ) {
        Icon(icon, contentDescription = null, tint = if (accent) Theme.accent else Theme.text2)
        Text(text, style = Theme.label, color = Theme.text)
    }
}
