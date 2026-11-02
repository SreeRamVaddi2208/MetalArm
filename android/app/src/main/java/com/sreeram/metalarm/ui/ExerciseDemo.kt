// The exercise's figure: what it works, drawn on the body. Served by the web
// app, so a new figure is a data import, not a release. The twin of iOS
// ExerciseDemo.

package com.sreeram.metalarm.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.FitnessCenter
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.unit.Dp
import coil3.compose.AsyncImage
import com.sreeram.metalarm.BuildConfig
import com.sreeram.metalarm.api.Exercise
import com.sreeram.metalarm.theme.Theme

/** Figures live at paths the web app serves ("/exercises/diagrams/x.png"). */
fun figureUrl(path: String?, base: String = BuildConfig.WEB_BASE_URL): String? =
    path?.takeIf { it.isNotEmpty() }?.let { base.trimEnd('/') + it }

/** The picture, or a plain icon while there is none to show. */
@Composable
fun FigureImage(path: String?, modifier: Modifier = Modifier, description: String? = null) {
    Box(modifier, contentAlignment = Alignment.Center) {
        var failed by remember(path) { mutableStateOf(false) }
        val url = figureUrl(path)
        if (url == null || failed) {
            Icon(Icons.Outlined.FitnessCenter, contentDescription = null, tint = Theme.text3)
        } else {
            AsyncImage(
                model = url, contentDescription = description, contentScale = ContentScale.Fit,
                onError = { failed = true }, modifier = Modifier.fillMaxSize(),
            )
        }
    }
}

@Composable
fun ExerciseDemo(exercise: Exercise, size: Dp, context: String = "demo") {
    val shape = RoundedCornerShape(Theme.radius)
    FigureImage(
        exercise.thumbnailUrl,
        Modifier
            .size(size)
            .clip(shape)
            .background(Theme.surface2, shape)
            .clearAndSetSemantics { contentDescription = "${exercise.name}: muscles worked" }
            .testTag(context + "Figure-" + exercise.name),
    )
}
