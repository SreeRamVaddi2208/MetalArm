// Searches the shared exercise library plus the user's own. From Train a tap
// adds the exercise; from the Library (`browsing`) it is a list to look
// through. The twin of iOS ExercisePickerView.

package com.sreeram.metalarm.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.SearchOff
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import com.sreeram.metalarm.api.capitalizedFirst
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.ButtonKind
import com.sreeram.metalarm.theme.EmptyState
import com.sreeram.metalarm.theme.MAButton
import com.sreeram.metalarm.theme.Theme
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExercisePicker(model: AppModel, browsing: Boolean = false, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var query by remember { mutableStateOf("") }
    LaunchedEffect(query) {
        // Debounce typing: a newer query cancels this one.
        delay(250)
        model.searchExercises(query)
    }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = Theme.surface,
        shape = RoundedCornerShape(topStart = Theme.radiusSheet, topEnd = Theme.radiusSheet),
        modifier = Modifier.testTag("exercisePicker"),
    ) {
        Column(Modifier.fillMaxHeight(0.92f).padding(horizontal = Theme.gutter), verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(if (browsing) "Exercises" else "Add exercise", style = Theme.title, color = Theme.text, modifier = Modifier.weight(1f))
                MAButton(if (browsing) "Done" else "Cancel", onDismiss, Modifier.testTag("pickerCancel"), kind = ButtonKind.Ghost)
            }
            Field(query, { query = it }, "Search exercises", "pickerSearch")
            if (model.pickerResults.isEmpty() && query.isNotBlank() && !model.isBusy) {
                EmptyState(Icons.Outlined.SearchOff, "No exercises match \"$query\".")
            }
            LazyColumn(Modifier.fillMaxWidth()) {
                items(model.pickerResults, key = { it.id }) { exercise ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .heightIn(min = Theme.rowMin)
                            .clickable(role = Role.Button) {
                                if (!browsing) scope.launch {
                                    model.addExercise(exercise)
                                    onDismiss()
                                }
                            }
                            .testTag("pickExercise-${exercise.name}")
                            .padding(vertical = Theme.Space.s4),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12),
                    ) {
                        ExerciseDemo(exercise, Theme.iconHit, context = "pickerDemo")
                        Column {
                            Text(exercise.name, style = Theme.body, color = Theme.text)
                            Text("${exercise.muscleLabel} · ${exercise.equipment.capitalizedFirst()}", style = Theme.caption, color = Theme.text2)
                        }
                    }
                }
            }
        }
    }
}
