// The Library tab: what you have kept - your routines, your programs, and the
// exercises you bookmarked. The twin of iOS SavedLibraryView.

package com.sreeram.metalarm.ui.library

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.rememberCoroutineScope
import com.sreeram.metalarm.api.ProgramDetail
import com.sreeram.metalarm.api.RoutineDetail
import com.sreeram.metalarm.theme.MAButton
import com.sreeram.metalarm.ui.ExerciseDemo
import kotlinx.coroutines.launch
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import com.sreeram.metalarm.api.SavedItem
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.EmptyState
import com.sreeram.metalarm.theme.ErrorState
import com.sreeram.metalarm.theme.ListRow
import com.sreeram.metalarm.theme.RowGroup
import com.sreeram.metalarm.theme.Screen
import com.sreeram.metalarm.theme.ScreenTitle
import com.sreeram.metalarm.theme.Segmented
import com.sreeram.metalarm.theme.Skeleton
import com.sreeram.metalarm.theme.Theme
import com.sreeram.metalarm.ui.FigureImage

private val parts = listOf("Routines" to "routines", "Programs" to "programs", "Saved" to "favorites")

@Composable
fun SavedLibrary(model: AppModel, onStarted: () -> Unit) {
    var part by remember { mutableStateOf("Routines") }
    var items by remember { mutableStateOf<List<SavedItem>?>(null) }
    var open by remember { mutableStateOf<SavedItem?>(null) }
    var plan by remember { mutableStateOf<SavedItem?>(null) }
    var error by remember { mutableStateOf("") }
    LaunchedEffect(part) {
        error = ""
        items = null
        runCatching { model.api.savedItems(parts.first { it.first == part }.second) }
            .onSuccess { items = it }
            .onFailure { if (it is kotlinx.coroutines.CancellationException) throw it else error = it.message.orEmpty() }
    }
    Screen {
        ScreenTitle("Library")
        Segmented(parts.map { it.first }, part, { part = it }, Modifier.testTag("savedParts"))
        val found = items
        when {
            error.isNotEmpty() -> ErrorState(error)
            found == null -> Skeleton()
            found.isEmpty() -> EmptyState(Icons.Outlined.BookmarkBorder, "Nothing here yet. Explore has plenty to keep.")
            else -> RowGroup {
                found.forEach { item ->
                    row {
                        if (item.type == "exercise") {
                            ListRow(item.title, Modifier.testTag("saved-item-${item.title}"), subtitle = item.subtitle.orEmpty(), chevron = true, onClick = { open = item }) {
                                FigureImage(item.image, Modifier.size(Theme.iconHit))
                            }
                        } else {
                            ListRow(item.title, Modifier.testTag("saved-item-${item.title}"), subtitle = item.subtitle.orEmpty(), chevron = true, onClick = { plan = item })
                        }
                    }
                }
            }
        }
    }
    open?.let { ExerciseSheet(model, it.id, it.title) { open = null } }
    plan?.let { item ->
        PlanSheet(model, item, onDismiss = { plan = null }) {
            plan = null
            onStarted()
        }
    }
}

/** A saved routine, with its exercises and Start; or a saved program, whose
 *  routines each lead to the same. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PlanSheet(model: AppModel, item: SavedItem, onDismiss: () -> Unit, onStarted: () -> Unit) {
    val scope = rememberCoroutineScope()
    var program by remember { mutableStateOf<ProgramDetail?>(null) }
    var routine by remember { mutableStateOf<RoutineDetail?>(null) }
    var error by remember { mutableStateOf("") }
    LaunchedEffect(item.id) {
        runCatching {
            if (item.type == "routine") routine = model.api.routine(item.id) else program = model.api.program(item.id)
        }.onFailure { if (it is kotlinx.coroutines.CancellationException) throw it else error = it.message.orEmpty() }
    }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = Theme.bg,
        shape = RoundedCornerShape(topStart = Theme.radiusSheet, topEnd = Theme.radiusSheet),
    ) {
        Column(
            Modifier.fillMaxHeight(0.92f).verticalScroll(rememberScrollState()).padding(horizontal = Theme.gutter).padding(bottom = Theme.Space.s24),
            verticalArrangement = Arrangement.spacedBy(Theme.Space.s12),
        ) {
            Text(routine?.name ?: item.title, style = Theme.title, color = Theme.text)
            val shownRoutine = routine
            val shownProgram = program
            when {
                error.isNotEmpty() -> ErrorState(error)
                shownRoutine != null -> {
                    RowGroup {
                        shownRoutine.exercises.forEach { slot ->
                            row {
                                ListRow(slot.exercise.name, subtitle = slot.targetLabel) {
                                    ExerciseDemo(slot.exercise, Theme.iconHit, context = "planDemo")
                                }
                            }
                        }
                    }
                    MAButton("Start", {
                        scope.launch {
                            if (model.startRoutine(shownRoutine.id)) onStarted() else error = model.errorMessage
                        }
                    }, Modifier.testTag("planStartButton"), enabled = !model.isBusy)
                }
                shownProgram != null -> RowGroup {
                    shownProgram.routines.forEach { entry ->
                        row {
                            ListRow(entry.name, Modifier.testTag("plan-routine-${entry.name}"),
                                subtitle = "${entry.exerciseCount} exercise${if (entry.exerciseCount == 1) "" else "s"}", chevron = true,
                                onClick = {
                                    scope.launch {
                                        runCatching { model.api.routine(entry.id) }
                                            .onSuccess { routine = it }
                                            .onFailure { error = it.message.orEmpty() }
                                    }
                                })
                        }
                    }
                }
                else -> Skeleton()
            }
        }
    }
}
