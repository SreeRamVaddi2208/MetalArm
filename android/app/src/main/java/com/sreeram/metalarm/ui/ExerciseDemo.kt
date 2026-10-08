// A muted, looping clip of the movement - or, with no clip yet, a placeholder
// of the same size so the layout never jumps. The twin of iOS ExerciseDemo.

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
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import com.sreeram.metalarm.api.Exercise
import com.sreeram.metalarm.theme.Theme

@Composable
fun ExerciseDemo(exercise: Exercise, size: Dp, context: String = "demo") {
    val url = exercise.mediaUrl
    val shape = RoundedCornerShape(Theme.radius)
    Box(
        Modifier
            .size(size)
            .clip(shape)
            .background(Theme.surface2, shape)
            .clearAndSetSemantics {
                contentDescription = if (url == null) "No demo for ${exercise.name} yet" else "Demo of ${exercise.name}"
            }
            .testTag(context + (if (url == null) "Placeholder-" else "Video-") + exercise.name),
        contentAlignment = Alignment.Center,
    ) {
        var failed by remember(url) { mutableStateOf(false) }
        if (url == null || failed) {
            Icon(Icons.Outlined.FitnessCenter, contentDescription = null, tint = Theme.text3)
        } else {
            // A clip that can't load falls back to the placeholder, never a black box.
            LoopingVideo(url) { failed = true }
        }
    }
}

/** Muted, looping, no controls; released the moment it leaves the screen. */
@androidx.annotation.OptIn(UnstableApi::class) // PlayerView's resize mode: stable in practice, still marked.
@Composable
private fun LoopingVideo(url: String, onFailed: () -> Unit) {
    val context = LocalContext.current
    val player = remember(url) {
        ExoPlayer.Builder(context).build().apply {
            volume = 0f
            repeatMode = Player.REPEAT_MODE_ONE
            setMediaItem(MediaItem.fromUri(url))
            prepare()
            playWhenReady = true
        }
    }
    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onPlayerError(error: androidx.media3.common.PlaybackException) = onFailed()
        }
        player.addListener(listener)
        onDispose {
            player.removeListener(listener)
            player.release()
        }
    }
    AndroidView(
        factory = {
            PlayerView(it).apply {
                useController = false
                // Until (or unless) a frame arrives, show the tile, not black.
                setShutterBackgroundColor(android.graphics.Color.TRANSPARENT)
                setBackgroundColor(android.graphics.Color.TRANSPARENT)
                resizeMode = AspectRatioFrameLayout.RESIZE_MODE_ZOOM
                this.player = player
            }
        },
        modifier = Modifier.fillMaxSize(),
    )
}
