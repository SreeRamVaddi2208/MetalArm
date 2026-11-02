// Explore's Exercises tab: the muscle and equipment grids, the figure cards
// they lead to, and one exercise's figure, muscles and steps. The twin of iOS
// ExploreExercises.

package com.sreeram.metalarm.ui.library

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sreeram.metalarm.api.Exercise
import com.sreeram.metalarm.api.ExerciseCard
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.ButtonKind
import com.sreeram.metalarm.theme.ErrorState
import com.sreeram.metalarm.theme.MAButton
import com.sreeram.metalarm.theme.SectionBlock
import com.sreeram.metalarm.theme.Skeleton
import com.sreeram.metalarm.theme.Theme
import com.sreeram.metalarm.ui.FigureImage
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private data class Tile(val code: String, val label: String)

// The browsable rows of backend/app/data/taxonomy.json.
private val muscleTiles = listOf(
    Tile("chest", "Chest"), Tile("biceps", "Biceps"), Tile("triceps", "Triceps"), Tile("back", "Back"),
    Tile("shoulders", "Shoulders"), Tile("abs", "Abs"), Tile("quads", "Quadriceps"), Tile("hamstrings", "Hamstrings"),
    Tile("glutes", "Glutes"), Tile("calves", "Calves"), Tile("forearms", "Forearms"), Tile("cardio", "Cardio"),
)
private val equipmentTiles = listOf(
    Tile("barbell", "Barbell"), Tile("dumbbell", "Dumbbell"), Tile("bodyweight", "Body weight"), Tile("cable", "Cable"),
    Tile("machine", "Machine"), Tile("smith_machine", "Smith machine"), Tile("kettlebell", "Kettlebell"), Tile("band", "Band"),
    Tile("ez_bar", "EZ bar"), Tile("trap_bar", "Trap bar"), Tile("cardio_machine", "Cardio machine"), Tile("other", "Other"),
)

/** Lays items out in rows of `columns`, inside the screen's own scroll. */
@Composable
private fun <T> Grid(items: List<T>, columns: Int, cell: @Composable (T) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
        items.chunked(columns).forEach { line ->
            Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
                line.forEach { Box(Modifier.weight(1f)) { cell(it) } }
                repeat(columns - line.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
fun ExploreExercises(model: AppModel, query: String) {
    val scope = rememberCoroutineScope()
    var muscle by remember { mutableStateOf<Tile?>(null) }
    var gear by remember { mutableStateOf<Tile?>(null) }
    var cards by remember { mutableStateOf<List<ExerciseCard>>(emptyList()) }
    var total by remember { mutableIntStateOf(0) }
    var cursor by remember { mutableStateOf<String?>(null) }
    var favorites by remember { mutableStateOf<Set<String>>(emptySet()) }
    var open by remember { mutableStateOf<Pair<String, String>?>(null) }
    var error by remember { mutableStateOf("") }
    val listing = muscle != null || gear != null || query.isNotBlank()

    suspend fun search(more: Boolean = false) {
        error = ""
        runCatching {
            if (favorites.isEmpty()) {
                favorites = model.api.savedItems("favorites").filter { it.type == "exercise" }.map { it.id }.toSet()
            }
            if (listing) {
                val page = model.api.browseExercises(query, muscle?.code, gear?.code, if (more) cursor else null)
                cards = if (more) cards + page.items else page.items
                total = page.total
                cursor = page.nextCursor
            }
        }.onFailure { if (it !is kotlinx.coroutines.CancellationException) error = it.message.orEmpty() else throw it }
    }

    LaunchedEffect(query, muscle, gear) {
        // Debounce typing: a newer query cancels this one.
        delay(250)
        search()
    }

    if (error.isNotEmpty()) {
        ErrorState(error, retry = { scope.launch { search() } })
    } else if (listing) {
        Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(muscle?.label ?: gear?.label ?: "Results", style = Theme.title, color = Theme.text, modifier = Modifier.weight(1f))
                if (muscle != null || gear != null) {
                    MAButton("Clear", { muscle = null; gear = null }, Modifier.testTag("exploreClear"), kind = ButtonKind.Ghost)
                }
            }
            Text("$total exercise${if (total == 1) "" else "s"}", style = Theme.caption, color = Theme.text2)
            Grid(cards, 2) { card ->
                FigureCard(card, card.id in favorites, { open = card.id to card.name }) {
                    scope.launch {
                        val on = card.id !in favorites
                        runCatching { model.api.setFavorite("exercise", card.id, on) }
                            .onSuccess { favorites = if (on) favorites + card.id else favorites - card.id }
                            .onFailure { error = it.message.orEmpty() }
                    }
                }
            }
            if (cursor != null) MAButton("Show more", { scope.launch { search(more = true) } }, kind = ButtonKind.Ghost)
        }
    } else {
        SectionBlock("Muscle Groups") {
            Grid(muscleTiles, 3) { tile ->
                Column(
                    Modifier.clickable(role = Role.Button) { muscle = tile }.testTag("muscle-${tile.code}"),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(Theme.Space.s4),
                ) {
                    FigureImage("/figures/muscles/${tile.code}.png", Modifier.fillMaxWidth().aspectRatio(1f))
                    Text(tile.label, style = Theme.label, color = Theme.text, textAlign = TextAlign.Center)
                }
            }
        }
        SectionBlock("Equipment") {
            Grid(equipmentTiles, 3) { tile ->
                Column(
                    Modifier.clickable(role = Role.Button) { gear = tile }.testTag("equipment-${tile.code}"),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(Theme.Space.s8),
                ) {
                    FigureImage(
                        "/figures/equipment/${tile.code}.png",
                        Modifier.fillMaxWidth().aspectRatio(1f).background(Theme.surface, CircleShape).padding(Theme.Space.s16),
                    )
                    Text(tile.label, style = Theme.label, color = Theme.text, textAlign = TextAlign.Center, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
        }
    }
    open?.let { (id, name) -> ExerciseSheet(model, id, name) { open = null } }
}

@Composable
private fun FigureCard(card: ExerciseCard, favorite: Boolean, onOpen: () -> Unit, onBookmark: () -> Unit) {
    val shape = RoundedCornerShape(Theme.radius)
    Box(Modifier.fillMaxWidth().clip(shape).background(Theme.surface2, shape)) {
        Column(Modifier.clickable(role = Role.Button, onClick = onOpen).testTag("exerciseCard-${card.name}")) {
            FigureImage(card.thumbnailUrl, Modifier.fillMaxWidth().aspectRatio(1f).background(Theme.surface), "${card.name}: muscles worked")
            Column(Modifier.padding(Theme.Space.s12), verticalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
                Text(card.name, style = Theme.label, color = Theme.text, minLines = 2, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(card.muscleLabel, style = Theme.caption, color = Theme.text2, maxLines = 1)
            }
        }
        Box(
            Modifier.size(Theme.iconHit).clickable(role = Role.Button, onClick = onBookmark).testTag("bookmark-${card.name}"),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                if (favorite) Icons.Filled.Bookmark else Icons.Outlined.BookmarkBorder,
                contentDescription = if (favorite) "Remove bookmark" else "Bookmark",
                tint = if (favorite) Theme.accent else Theme.text2,
            )
        }
    }
}

/** One exercise: the large figure, what it works, and how to do it. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExerciseSheet(model: AppModel, id: String, name: String, onDismiss: () -> Unit) {
    var exercise by remember(id) { mutableStateOf<Exercise?>(null) }
    var error by remember(id) { mutableStateOf("") }
    LaunchedEffect(id) {
        runCatching { model.api.exercise(id) }.onSuccess { exercise = it }.onFailure { error = it.message.orEmpty() }
    }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = Theme.bg,
        shape = RoundedCornerShape(topStart = Theme.radiusSheet, topEnd = Theme.radiusSheet),
        modifier = Modifier.testTag("exerciseSheet"),
    ) {
        Column(
            Modifier.fillMaxHeight(0.92f).verticalScroll(rememberScrollState()).padding(horizontal = Theme.gutter).padding(bottom = Theme.Space.s24),
            verticalArrangement = Arrangement.spacedBy(Theme.Space.s12),
        ) {
            Text(name, style = Theme.title, color = Theme.text)
            val found = exercise
            when {
                found != null -> {
                    FigureImage(
                        found.illustrationUrl ?: found.thumbnailUrl,
                        Modifier.fillMaxWidth().aspectRatio(1f).background(Theme.surface, RoundedCornerShape(Theme.radius)).testTag("exerciseSheetFigure"),
                        "${found.name}: muscles worked",
                    )
                    Text(found.muscleLabel, style = Theme.label, color = Theme.text)
                    if (found.secondaryMuscleGroups.isNotEmpty()) Text("Also: ${found.secondaryLabel}", style = Theme.caption, color = Theme.text2)
                    found.howTo.forEachIndexed { index, step -> Text("${index + 1}. $step", style = Theme.body, color = Theme.text) }
                    found.figureCredit?.let { Text(it, style = Theme.caption, color = Theme.text3) }
                }
                error.isEmpty() -> Skeleton(height = 280.dp)
                else -> ErrorState(error)
            }
        }
    }
}
