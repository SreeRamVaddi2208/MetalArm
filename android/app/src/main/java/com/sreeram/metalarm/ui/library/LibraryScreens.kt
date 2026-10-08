// The Library tab - the twins of iOS LibraryHomeView, LibraryPathView,
// LibraryProgramView and LibraryWorkoutView. Your program first (its Start is
// the only accent fill), what is recommended for your path, then the other
// paths and the exercise list. Two taps to a workout. What leads, and in what
// order, is the server's decision.

package com.sreeram.metalarm.ui.library

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.FitnessCenter
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.sreeram.metalarm.api.LibraryFilters
import com.sreeram.metalarm.api.LibraryHome
import com.sreeram.metalarm.api.LibraryProgram
import com.sreeram.metalarm.api.LibraryVocabulary
import com.sreeram.metalarm.api.LibraryWorkout
import com.sreeram.metalarm.api.LibraryWorkoutExercise
import com.sreeram.metalarm.api.YourProgram
import com.sreeram.metalarm.api.plural
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.ButtonKind
import com.sreeram.metalarm.theme.Chip
import com.sreeram.metalarm.theme.EmptyState
import com.sreeram.metalarm.theme.ErrorState
import com.sreeram.metalarm.theme.IconButton
import com.sreeram.metalarm.theme.ListRow
import com.sreeram.metalarm.theme.MAButton
import com.sreeram.metalarm.theme.Pill
import com.sreeram.metalarm.theme.RowGroup
import com.sreeram.metalarm.theme.Screen
import com.sreeram.metalarm.theme.ScreenTitle
import com.sreeram.metalarm.theme.SectionBlock
import com.sreeram.metalarm.theme.Skeleton
import com.sreeram.metalarm.theme.StatTile
import com.sreeram.metalarm.theme.Theme
import com.sreeram.metalarm.theme.bleed
import com.sreeram.metalarm.theme.card
import com.sreeram.metalarm.ui.ExerciseDemo
import com.sreeram.metalarm.ui.ExercisePicker
import com.sreeram.metalarm.ui.TopBar
import com.sreeram.metalarm.ui.TrainingPathScreen
import kotlinx.coroutines.launch

@Composable
fun LibraryTab(model: AppModel, nav: NavHostController, onStarted: () -> Unit) {
    NavHost(nav, startDestination = "library") {
        composable("library") {
            LibraryHomeScreen(
                model,
                onPath = { nav.navigate("path/$it") },
                onProgram = { nav.navigate("program/$it") },
                onWorkout = { nav.navigate("workout/$it") },
                onStarted = onStarted,
            )
        }
        composable("path/{category}") { entry ->
            LibraryPathScreen(model, entry.arguments?.getString("category") ?: "athlete",
                onBack = { nav.popBackStack() }, onProgram = { nav.navigate("program/$it") }, onWorkout = { nav.navigate("workout/$it") })
        }
        composable("program/{slug}") { entry ->
            LibraryProgramScreen(model, entry.arguments?.getString("slug") ?: "",
                onBack = { nav.popBackStack() }, onWorkout = { nav.navigate("workout/$it") }, onStarted = onStarted)
        }
        composable("workout/{slug}") { entry ->
            LibraryWorkoutScreen(model, entry.arguments?.getString("slug") ?: "", onBack = { nav.popBackStack() }, onStarted = onStarted)
        }
    }
}

// MARK: Home

@Composable
fun LibraryHomeScreen(
    model: AppModel,
    onPath: (String) -> Unit,
    onProgram: (String) -> Unit,
    onWorkout: (String) -> Unit,
    onStarted: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var choosingPath by remember { mutableStateOf(false) }
    var browsingExercises by remember { mutableStateOf(false) }
    val own = model.libraryHome?.path?.takeIf { it.isNotEmpty() } ?: model.me?.characterClass.orEmpty()
    LaunchedEffect(Unit) { model.loadLibraryHome() }

    if (choosingPath) {
        Column {
            Row(Modifier.padding(horizontal = Theme.gutter).padding(top = Theme.Space.s8)) {
                TopBar("Training path", { choosingPath = false })
            }
            TrainingPathScreen(model, isOnboarding = false) {
                choosingPath = false
                scope.launch { model.loadLibraryHome() }
            }
        }
        return
    }
    Screen {
        ScreenTitle("Library") {
            IconButton(Icons.Filled.Search, "Search and filter", { onPath(own.ifEmpty { "athlete" }) }, Modifier.testTag("librarySearchButton"))
        }
        PathChips(own, own, onPath)
        val home = model.libraryHome
        when {
            home != null -> HomeContent(model, home, onPath, onProgram, onWorkout, onStarted, { choosingPath = true }, { browsingExercises = true })
            model.errorMessage.isEmpty() -> Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
                Skeleton(height = 120.dp)
                Skeleton(height = 160.dp)
                Skeleton()
            }
            else -> ErrorState(model.errorMessage) { /* retried by pull-in */ }
        }
    }
    if (browsingExercises) ExercisePicker(model, browsing = true) { browsingExercises = false }
}

@Composable
private fun HomeContent(
    model: AppModel, home: LibraryHome,
    onPath: (String) -> Unit, onProgram: (String) -> Unit, onWorkout: (String) -> Unit, onStarted: () -> Unit,
    onChoosePath: () -> Unit, onExercises: () -> Unit,
) {
    home.yourProgram?.let { YourProgramCard(model, it, onProgram, onWorkout, onStarted) }
    if (home.needsPath) {
        Column(Modifier.card(), verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
            Text("Pick your training path", style = Theme.title, color = Theme.text)
            Text(
                "The Library leads with programs and workouts made for how you train. Until then, here is everything.",
                style = Theme.body, color = Theme.text2,
            )
            MAButton("Choose your path", onChoosePath, Modifier.testTag("choosePathButton"))
        }
    } else {
        SectionBlock("Recommended for you", action = "See all", onAction = { onPath(home.path) }) {
            Row(
                Modifier.bleed().horizontalScroll(rememberScrollState()).padding(horizontal = Theme.gutter),
                horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12),
            ) {
                home.recommendedPrograms.forEach { ProgramCard(it, { onProgram(it.slug) }, Modifier.width(280.dp)) }
            }
            if (home.recommendedWorkouts.isNotEmpty()) {
                Text("Workouts", style = Theme.caption, color = Theme.text2)
                RowGroup { home.recommendedWorkouts.forEach { w -> row { WorkoutRow(w) { onWorkout(w.slug) } } } }
            }
        }
    }
    SectionBlock(if (home.needsPath) "Browse by path" else "Explore other paths") {
        RowGroup {
            home.otherPaths.forEach { other ->
                row {
                    ListRow(
                        other.label, Modifier.testTag("library-path-${other.category}"),
                        subtitle = "${plural(other.programs, "program")} · ${plural(other.workouts, "workout")}",
                        chevron = true, onClick = { onPath(other.category) },
                    )
                }
            }
        }
    }
    RowGroup {
        row {
            ListRow("Exercises", Modifier.testTag("libraryExercisesRow"), subtitle = "Every exercise, by muscle and equipment",
                chevron = true, onClick = onExercises) { Icon(Icons.Filled.Search, contentDescription = null, tint = Theme.text2) }
        }
    }
}

@Composable
private fun YourProgramCard(
    model: AppModel, yours: YourProgram, onProgram: (String) -> Unit, onWorkout: (String) -> Unit, onStarted: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    Column(Modifier.card().testTag("yourProgramCard"), verticalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
        Text("Your program", style = Theme.caption, color = Theme.text2)
        ListRow(yours.program.name, subtitle = yours.enrollment.whereLabel, chevron = true, onClick = { onProgram(yours.program.slug) })
        yours.enrollment.nextWorkout?.let { next ->
            ListRow("Next: ${next.name}", subtitle = next.meta, chevron = true, onClick = { onWorkout(next.slug) })
            MAButton("Start", { scope.launch { if (model.startLibraryWorkout(next.slug)) onStarted() } },
                Modifier.testTag("yourProgramStartButton"), icon = Icons.Filled.PlayArrow, enabled = !model.isBusy)
        }
    }
}

// MARK: Path

@Composable
fun LibraryPathScreen(
    model: AppModel, initial: String, onBack: () -> Unit, onProgram: (String) -> Unit, onWorkout: (String) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var category by rememberSaveable { mutableStateOf(initial) }
    var filtering by remember { mutableStateOf(false) }
    var loaded by remember { mutableStateOf(false) }
    val own = model.libraryHome?.path?.takeIf { it.isNotEmpty() } ?: model.me?.characterClass.orEmpty()
    LaunchedEffect(category, model.libraryFilters) {
        model.loadLibraryPath(category)
        loaded = true
    }
    val clear: () -> Unit = { model.libraryFilters = LibraryFilters() }

    Screen {
        TopBar(LibraryVocabulary.pathLabel(category), onBack) {
            IconButton(Icons.Filled.Tune, "Filter", { filtering = true }, Modifier.testTag("libraryFilterButton"),
                badge = !model.libraryFilters.isEmpty)
        }
        PathChips(category, own) { category = it }
        if (!model.libraryFilters.isEmpty) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("${plural(model.libraryFilters.count, "filter")} on", style = Theme.caption, color = Theme.text2,
                    modifier = Modifier.weight(1f).testTag("filtersOnText"))
                MAButton("Clear", clear, Modifier.testTag("clearFiltersButton"), kind = ButtonKind.Ghost)
            }
        }
        if (!loaded) {
            Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
                Skeleton(height = 120.dp)
                Skeleton(height = 120.dp)
                Skeleton()
            }
        } else {
            ErrorState(model.errorMessage) { scope.launch { model.loadLibraryPath(category) } }
            SectionBlock("Programs") {
                if (model.libraryPrograms.isEmpty()) {
                    EmptyState(Icons.Outlined.CalendarMonth, "No programs match these filters.") {
                        MAButton("Clear filters", clear, kind = ButtonKind.Secondary, full = false, enabled = !model.libraryFilters.isEmpty)
                    }
                } else {
                    model.libraryPrograms.forEach { ProgramCard(it, { onProgram(it.slug) }, showPill = false) }
                }
            }
            SectionBlock("Workouts") {
                if (model.libraryWorkouts.isEmpty()) {
                    EmptyState(Icons.Outlined.FitnessCenter, "No workouts match these filters.") {
                        MAButton("Clear filters", clear, kind = ButtonKind.Secondary, full = false, enabled = !model.libraryFilters.isEmpty)
                    }
                } else {
                    RowGroup { model.libraryWorkouts.forEach { w -> row { WorkoutRow(w) { onWorkout(w.slug) } } } }
                }
            }
        }
    }
    if (filtering) FilterSheet(model.libraryFilters, onDismiss = { filtering = false }) { model.libraryFilters = it; filtering = false }
}

/** Chips in four groups; nothing changes until Show results. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FilterSheet(initial: LibraryFilters, onDismiss: () -> Unit, onApply: (LibraryFilters) -> Unit) {
    var filters by remember { mutableStateOf(initial) }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = Theme.surface,
        shape = RoundedCornerShape(topStart = Theme.radiusSheet, topEnd = Theme.radiusSheet),
    ) {
        Column(Modifier.padding(horizontal = Theme.gutter).padding(bottom = Theme.Space.s16).fillMaxHeight(0.85f), verticalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
            Text("Filter", style = Theme.title, color = Theme.text)
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(Theme.Space.s24)) {
                Group("Days a week") {
                    LibraryVocabulary.days.forEach { d ->
                        Chip("$d", { filters = filters.copy(daysPerWeek = if (filters.daysPerWeek == d) null else d) }, selected = filters.daysPerWeek == d)
                    }
                }
                Group("Difficulty") {
                    LibraryVocabulary.difficulties.forEach { level ->
                        Chip(LibraryVocabulary.label(level), { filters = filters.copy(difficulty = if (filters.difficulty == level) null else level) },
                            selected = filters.difficulty == level)
                    }
                }
                Group("Equipment you have") {
                    LibraryVocabulary.equipment.forEach { kit ->
                        Chip(LibraryVocabulary.label(kit), {
                            filters = filters.copy(equipment = if (kit in filters.equipment) filters.equipment - kit else filters.equipment + kit)
                        }, selected = kit in filters.equipment)
                    }
                }
                Group("Workout length") {
                    LibraryVocabulary.durations.forEach { minutes ->
                        Chip("Up to $minutes min", { filters = filters.copy(maxMinutes = if (filters.maxMinutes == minutes) null else minutes) },
                            Modifier.testTag("duration-$minutes"), selected = filters.maxMinutes == minutes)
                    }
                }
                MAButton("Clear filters", { filters = LibraryFilters() }, kind = ButtonKind.Ghost, full = true)
            }
            MAButton("Show results", { onApply(filters) }, Modifier.testTag("showResultsButton"))
        }
    }
}

@Composable
private fun Group(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
        Text(title, style = Theme.caption, color = Theme.text2)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s8)) { content() }
    }
}

// MARK: Program

@Composable
fun LibraryProgramScreen(model: AppModel, slug: String, onBack: () -> Unit, onWorkout: (String) -> Unit, onStarted: () -> Unit) {
    val scope = rememberCoroutineScope()
    LaunchedEffect(slug) { model.loadLibraryProgram(slug) }
    val program = model.libraryProgram?.takeIf { it.slug == slug }

    Screen(pinned = program?.let { p -> { ProgramPrimary(model, p, onStarted) } }) {
        TopBar("", onBack)
        if (program != null) {
            Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
                Text(program.name, style = Theme.titleLG, color = Theme.text)
                Pill(program.categoryLabel, accent = false)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
                StatTile("${program.weeks}", "Weeks", Modifier.weight(1f))
                StatTile("${program.daysPerWeek}", "Days a week", Modifier.weight(1f))
                StatTile(LibraryVocabulary.label(program.difficulty), "Level", Modifier.weight(1f))
            }
            program.description?.takeIf { it.isNotEmpty() }?.let { Text(it, style = Theme.body, color = Theme.text2) }
            program.enrollment?.takeIf { it.status == "active" }?.let { enrollment ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Following · ${enrollment.whereLabel}", style = Theme.caption, color = Theme.text2, modifier = Modifier.weight(1f))
                    MAButton("Pause", { scope.launch { model.unfollowProgram(slug) } }, Modifier.testTag("pauseProgramButton"), kind = ButtonKind.Ghost)
                }
            }
            SectionBlock("Schedule") { ScheduleGrid(program.schedule, onWorkout) }
            SectionBlock("Workouts in this program") {
                RowGroup { program.workouts.forEach { w -> row { WorkoutRow(w) { onWorkout(w.slug) } } } }
            }
            Text(LibraryVocabulary.NOTE, style = Theme.caption, color = Theme.text2)
        } else if (model.errorMessage.isEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
                Skeleton(height = 96.dp)
                Skeleton(height = 64.dp)
                Skeleton(height = 200.dp)
            }
        }
        ErrorState(model.errorMessage) { scope.launch { model.loadLibraryProgram(slug) } }
    }
}

@Composable
private fun ProgramPrimary(model: AppModel, program: LibraryProgram, onStarted: () -> Unit) {
    val scope = rememberCoroutineScope()
    val enrollment = program.enrollment
    val next = enrollment?.nextWorkout
    when {
        enrollment?.status == "active" && next != null -> MAButton(
            "Start next: ${next.name}", { scope.launch { if (model.startLibraryWorkout(next.slug)) onStarted() } },
            Modifier.testTag("startNextButton"), icon = Icons.Filled.PlayArrow, enabled = !model.isBusy,
        )
        else -> {
            val label = when (enrollment?.status) {
                "active" -> "Follow again"
                "paused" -> "Resume program"
                "completed" -> "Start it again"
                else -> "Follow program"
            }
            MAButton(label, { scope.launch { model.followProgram(program.slug) } }, Modifier.testTag("followProgramButton"), enabled = !model.isBusy)
        }
    }
}

// MARK: Workout

@Composable
fun LibraryWorkoutScreen(model: AppModel, slug: String, onBack: () -> Unit, onStarted: () -> Unit) {
    val scope = rememberCoroutineScope()
    var saved by remember { mutableStateOf(false) }
    LaunchedEffect(slug) {
        model.libraryNotice = ""
        model.loadLibraryWorkout(slug)
        saved = model.libraryWorkout?.routineId != null
    }
    val workout = model.libraryWorkout?.takeIf { it.slug == slug }

    Screen(
        pinned = workout?.let {
            {
                MAButton(if (model.isBusy) "Starting…" else "Start workout",
                    { scope.launch { if (model.startLibraryWorkout(slug)) onStarted() } },
                    Modifier.testTag("libraryStartButton"), icon = Icons.Filled.PlayArrow, enabled = !model.isBusy)
            }
        },
    ) {
        TopBar("", onBack)
        if (workout != null) {
            WorkoutContent(model, workout, saved) {
                scope.launch {
                    model.saveLibraryWorkout(slug)
                    if (model.libraryNotice.isNotEmpty()) saved = true
                }
            }
        } else if (model.errorMessage.isEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
                Skeleton(height = 96.dp)
                Skeleton()
                Skeleton()
            }
        }
        ErrorState(model.errorMessage)
    }
}

@Composable
private fun WorkoutContent(model: AppModel, workout: LibraryWorkout, saved: Boolean, onSave: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
        Text(workout.name, style = Theme.titleLG, color = Theme.text)
        Pill(workout.categoryLabel, accent = false)
    }
    Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
        StatTile("${workout.durationMinutes}", "Minutes", Modifier.weight(1f))
        StatTile("${workout.exerciseCount}", "Exercises", Modifier.weight(1f))
    }
    Text(workout.equipment.joinToString(", ") { LibraryVocabulary.label(it) }, style = Theme.caption, color = Theme.text2)
    workout.description?.takeIf { it.isNotEmpty() }?.let { Text(it, style = Theme.body, color = Theme.text2) }
    RowGroup { workout.exercises.forEach { slot -> row { ExerciseRow(slot) } } }
    if (model.libraryNotice.isNotEmpty()) {
        Text(model.libraryNotice, style = Theme.caption, color = Theme.text2, modifier = Modifier.testTag("libraryNotice"))
    }
    MAButton(if (saved) "In your routines" else "Save to routines", onSave, Modifier.testTag("saveRoutineButton"),
        kind = ButtonKind.Secondary, icon = Icons.Filled.Bookmark, enabled = !saved && !model.isBusy)
}

@Composable
private fun ExerciseRow(slot: LibraryWorkoutExercise) {
    val muscle = slot.exercise.primaryMuscleGroups.firstOrNull()?.let { LibraryVocabulary.label(it) }.orEmpty()
    val superset = if (slot.supersetGroup > 0) "Superset ${slot.supersetGroup} · " else ""
    Column(Modifier.testTag("library-exercise-${slot.position}")) {
        ListRow(slot.exercise.name, subtitle = listOf(muscle, superset + slot.target).filter { it.isNotEmpty() }.joinToString(" · ")) {
            ExerciseDemo(slot.exercise, Theme.iconHit, context = "libraryExerciseDemo")
        }
        slot.note?.takeIf { it.isNotEmpty() }?.let {
            Text(it, style = Theme.caption, color = Theme.text3, modifier = Modifier.padding(bottom = Theme.Space.s8))
        }
    }
}
