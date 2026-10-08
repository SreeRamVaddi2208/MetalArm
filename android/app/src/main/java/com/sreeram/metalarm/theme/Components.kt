// The primitives every screen is built from - the Android twins of the iOS
// app's Theme/Components.swift and the web app's frontend/metalarm/ui/. One
// primary button per screen, pinned low (`Screen(pinned = …)`); everything
// else secondary, ghost or danger. No shadows, no gradients outside reward
// moments.

package com.sreeram.metalarm.theme

import android.provider.Settings
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.layout
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import com.sreeram.metalarm.api.RankTitle
import kotlin.math.roundToInt

// MARK: Buttons

enum class ButtonKind { Primary, Secondary, Ghost, Danger }

/** 52 dp, full pill. ONE Primary per screen. */
@Composable
fun MAButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    kind: ButtonKind = ButtonKind.Primary,
    full: Boolean = kind != ButtonKind.Ghost,
    icon: ImageVector? = null,
    enabled: Boolean = true,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val foreground = when (kind) {
        ButtonKind.Primary -> Theme.onAccent
        ButtonKind.Danger -> Theme.danger
        else -> Theme.text
    }
    val background = when (kind) {
        ButtonKind.Primary -> Theme.accent.copy(alpha = if (pressed) 0.85f else 1f)
        else -> if (pressed) Theme.surface2 else Color.Transparent
    }
    val outline = when (kind) {
        ButtonKind.Secondary -> BorderStroke(1.dp, Theme.border)
        ButtonKind.Danger -> BorderStroke(1.dp, Theme.danger)
        else -> null
    }
    Row(
        modifier = modifier
            .then(if (full) Modifier.fillMaxWidth() else Modifier)
            .heightIn(min = Theme.buttonHeight)
            .clip(CircleShape)
            .background(background, CircleShape)
            .then(if (outline != null) Modifier.border(outline, CircleShape) else Modifier)
            .clickable(interaction, indication = null, enabled = enabled, role = Role.Button, onClick = onClick)
            .alpha(if (enabled) 1f else 0.4f)
            .padding(horizontal = Theme.Space.s24),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = null, tint = foreground, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(Theme.Space.s8))
        }
        Text(text, style = Theme.label, color = foreground, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

/** A 44 dp icon target with no background. */
@Composable
fun IconButton(
    icon: ImageVector,
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    badge: Boolean = false,
    tint: Color = Theme.text2,
) {
    Box(
        modifier = modifier
            .size(Theme.iconHit)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = tint)
        if (badge) {
            Box(
                Modifier
                    .align(Alignment.TopEnd)
                    .padding(Theme.Space.s8)
                    .size(Theme.Space.s8)
                    .background(Theme.accent, CircleShape),
            )
        }
    }
}

// MARK: Surfaces, screens and rows

/** Surface, 12 dp radius, 16 dp padding. No border, no shadow. */
fun Modifier.card(padding: Dp = Theme.cardPadding): Modifier =
    fillMaxWidth().background(Theme.surface, RoundedCornerShape(Theme.radius)).padding(padding)

/**
 * The standard screen: a scrolling column with gutters, the background, and
 * the screen's one primary action pinned low (above the tab bar) when there
 * is one. `top` adds the status-bar inset for a tab's root screen.
 */
@Composable
fun Screen(
    modifier: Modifier = Modifier,
    pinned: (@Composable () -> Unit)? = null,
    scroll: Boolean = true,
    top: Boolean = true,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier
            .fillMaxSize()
            .background(Theme.bg)
            .then(if (top) Modifier.windowInsetsPadding(WindowInsets.statusBars) else Modifier)
            .imePadding(),
    ) {
        Column(
            Modifier
                .weight(1f)
                .fillMaxWidth()
                .then(if (scroll) Modifier.verticalScroll(rememberScrollState()) else Modifier)
                .padding(horizontal = Theme.gutter, vertical = Theme.Space.s16),
            verticalArrangement = Arrangement.spacedBy(Theme.Space.s24),
            content = content,
        )
        if (pinned != null) {
            Box(
                Modifier
                    .fillMaxWidth()
                    .background(Theme.bg)
                    .padding(start = Theme.gutter, end = Theme.gutter, top = Theme.Space.s12, bottom = Theme.Space.s8),
            ) { pinned() }
        }
    }
}

/** Title, subtitle, and an optional trailing value or chevron. 56 dp minimum. */
@Composable
fun ListRow(
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String = "",
    trailing: String = "",
    chevron: Boolean = false,
    titleColor: Color = Theme.text,
    onClick: (() -> Unit)? = null,
    leading: (@Composable () -> Unit)? = null,
) {
    Row(
        modifier
            .fillMaxWidth()
            .heightIn(min = Theme.rowMin)
            .then(if (onClick != null) Modifier.clickable(role = Role.Button, onClick = onClick) else Modifier),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12),
    ) {
        leading?.invoke()
        Column(Modifier.weight(1f)) {
            Text(title, style = Theme.body, color = titleColor, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (subtitle.isNotEmpty()) {
                Text(subtitle, style = Theme.caption, color = Theme.text2, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
        }
        if (trailing.isNotEmpty()) Text(trailing, style = Theme.body, color = Theme.text2)
        if (chevron) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = null, tint = Theme.text3)
        }
    }
}

/** Collects the rows of a RowGroup. */
class RowGroupScope {
    internal val rows = mutableListOf<@Composable () -> Unit>()
    fun row(content: @Composable () -> Unit) { rows += content }
}

/** Rows separated by hairlines. */
@Composable
fun RowGroup(modifier: Modifier = Modifier, build: RowGroupScope.() -> Unit) {
    val scope = RowGroupScope().apply(build)
    Column(modifier.fillMaxWidth()) {
        scope.rows.forEachIndexed { index, row ->
            if (index > 0) Box(Modifier.fillMaxWidth().height(1.dp).background(Theme.border))
            row()
        }
    }
}

/** A titled group of content: spaced, not boxed. */
@Composable
fun SectionBlock(
    title: String,
    modifier: Modifier = Modifier,
    action: String = "",
    onAction: () -> Unit = {},
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(title, style = Theme.title, color = Theme.text, modifier = Modifier.weight(1f).semantics { heading() })
            if (action.isNotEmpty()) {
                Row(
                    Modifier
                        .heightIn(min = Theme.touch)
                        .clickable(role = Role.Button, onClick = onAction),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(action, style = Theme.label, color = Theme.text2)
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = null, tint = Theme.text2)
                }
            }
        }
        content()
    }
}

// MARK: Controls

/** A pill: surface-2, accent-soft with accent text when selected. */
@Composable
fun Chip(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    selected: Boolean = false,
    dot: Boolean = false,
) {
    Row(
        modifier
            .heightIn(min = Theme.touch)
            .padding(vertical = Theme.Space.s4)
            .clip(CircleShape)
            .background(if (selected) Theme.accentSoft else Theme.surface2, CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { this.selected = selected }
            .padding(horizontal = Theme.Space.s16),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Theme.Space.s8),
    ) {
        if (dot) {
            Box(
                Modifier
                    .size(6.dp)
                    .background(if (selected) Theme.accent else Theme.text2, CircleShape)
                    .semantics { contentDescription = "Your path" },
            )
        }
        Text(label, style = Theme.label, color = if (selected) Theme.accent else Theme.text, maxLines = 1)
    }
}

/** A row of chips that scrolls sideways and bleeds to the screen edge. */
@Composable
fun ChipRow(modifier: Modifier = Modifier, content: @Composable RowScope.() -> Unit) {
    Row(
        modifier
            .bleed()
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = Theme.gutter),
        horizontalArrangement = Arrangement.spacedBy(Theme.Space.s8),
        verticalAlignment = Alignment.CenterVertically,
        content = content,
    )
}

/** Widens a child of a gutter-padded column back to the screen edges. */
fun Modifier.bleed(): Modifier = layout { measurable, constraints ->
    val extra = (Theme.gutter.toPx() * 2).roundToInt()
    val placeable = measurable.measure(
        constraints.copy(
            maxWidth = if (constraints.hasBoundedWidth) constraints.maxWidth + extra else constraints.maxWidth,
            minWidth = if (constraints.hasBoundedWidth) constraints.maxWidth + extra else constraints.minWidth,
        ),
    )
    layout(placeable.width - extra, placeable.height) { placeable.place(-extra / 2, 0) }
}

/** 2-4 options on a surface track. */
@Composable
fun Segmented(
    options: List<String>,
    selected: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier
            .background(Theme.surface, CircleShape)
            .padding(Theme.Space.s4),
        horizontalArrangement = Arrangement.spacedBy(Theme.Space.s4),
    ) {
        options.forEach { option ->
            val on = option == selected
            Box(
                Modifier
                    .weight(1f)
                    .heightIn(min = 40.dp)
                    .clip(CircleShape)
                    .background(if (on) Theme.surface2 else Color.Transparent, CircleShape)
                    .clickable(role = Role.Tab) { onSelect(option) }
                    .semantics { this.selected = on },
                contentAlignment = Alignment.Center,
            ) {
                Text(option, style = Theme.label, color = if (on) Theme.text else Theme.text2)
            }
        }
    }
}

/** A number, its unit, and a small label under it. Groups of 2-3. */
@Composable
fun StatTile(
    value: String,
    label: String,
    modifier: Modifier = Modifier,
    unit: String = "",
    big: Boolean = false,
) {
    Column(modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
            Text(value, style = if (big) Theme.display else Theme.title, color = Theme.text, maxLines = 1)
            if (unit.isNotEmpty()) Text(unit, style = Theme.caption, color = Theme.text2)
        }
        Text(label, style = Theme.caption, color = Theme.text2)
    }
}

/** 4 dp track in surface-2, accent fill. */
@Composable
fun ProgressBar(progress: Double, modifier: Modifier = Modifier, label: String = "") {
    val fraction = progress.coerceIn(0.0, 1.0).toFloat()
    Column(
        modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = label.ifEmpty { "Progress" }
                stateDescription = "${(fraction * 100).roundToInt()} percent"
            },
        verticalArrangement = Arrangement.spacedBy(Theme.Space.s8),
    ) {
        Box(Modifier.fillMaxWidth().height(Theme.Space.s4).background(Theme.surface2, CircleShape)) {
            Box(Modifier.fillMaxWidth(fraction).height(Theme.Space.s4).background(Theme.accent, CircleShape))
        }
        if (label.isNotEmpty()) Text(label, style = Theme.caption, color = Theme.text2)
    }
}

/** A small tag - the "PR" pill. */
@Composable
fun Pill(label: String, modifier: Modifier = Modifier, accent: Boolean = true) {
    Text(
        label,
        style = Theme.caption.copy(fontWeight = FontWeight.Bold),
        color = if (accent) Theme.accent else Theme.text2,
        modifier = modifier
            .background(if (accent) Theme.accentSoft else Theme.surface2, CircleShape)
            .padding(horizontal = Theme.Space.s8, vertical = 2.dp),
    )
}

/** The rank as a hexagon in its tier colour - the only tier colour outside
 *  the rank-up overlay. */
@Composable
fun RankBadge(rank: String, modifier: Modifier = Modifier, size: Dp = 48.dp) {
    val tint = Theme.tier(rank)
    Box(
        modifier
            .size(size)
            .border(BorderStroke(maxOf(2.dp, size / 16), tint), Hexagon)
            .semantics(mergeDescendants = false) { contentDescription = "Rank ${RankTitle.of(rank)}" },
        contentAlignment = Alignment.Center,
    ) {
        val style = when {
            size >= 96.dp -> Theme.display
            size >= 48.dp -> Theme.title
            else -> Theme.caption.copy(fontWeight = FontWeight.Bold)
        }
        Text(rank.uppercase(), style = style, color = tint)
    }
}

/** A flat-topped hexagon. */
object Hexagon : Shape {
    override fun createOutline(size: Size, layoutDirection: LayoutDirection, density: Density): Outline {
        val w = size.width
        val h = size.height
        val path = Path().apply {
            moveTo(w * 0.25f, h * 0.05f)
            lineTo(w * 0.75f, h * 0.05f)
            lineTo(w, h * 0.5f)
            lineTo(w * 0.75f, h * 0.95f)
            lineTo(w * 0.25f, h * 0.95f)
            lineTo(0f, h * 0.5f)
            close()
        }
        return Outline.Generic(path)
    }
}

/** Neutral initials circle. Rank is shown by a RankBadge beside it. */
@Composable
fun Avatar(initials: String, modifier: Modifier = Modifier, size: Dp = 40.dp) {
    Box(modifier.size(size).background(Theme.surface2, CircleShape), contentAlignment = Alignment.Center) {
        val style = when {
            size >= 96.dp -> Theme.titleLG
            size >= 48.dp -> Theme.title
            else -> Theme.label
        }
        Text(initials, style = style, color = Theme.text2)
    }
}

// MARK: States

/** One icon, one sentence, at most one (secondary) action. */
@Composable
fun EmptyState(
    icon: ImageVector,
    line: String,
    modifier: Modifier = Modifier,
    action: (@Composable () -> Unit)? = null,
) {
    Column(
        modifier.fillMaxWidth().padding(vertical = Theme.Space.s32),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(Theme.Space.s12),
    ) {
        Icon(icon, contentDescription = null, tint = Theme.text3)
        Text(line, style = Theme.body, color = Theme.text2, textAlign = TextAlign.Center)
        action?.invoke()
    }
}

/** What went wrong, in a sentence, and Try again. Calm: danger red is for
 *  destructive actions only. */
@Composable
fun ErrorState(message: String, modifier: Modifier = Modifier, retry: (() -> Unit)? = null) {
    if (message.isEmpty()) return
    Row(
        modifier.fillMaxWidth().semantics(mergeDescendants = true) {},
        horizontalArrangement = Arrangement.spacedBy(Theme.Space.s8),
        verticalAlignment = Alignment.Top,
    ) {
        Icon(Icons.Outlined.ErrorOutline, contentDescription = null, tint = Theme.text2)
        Text(message, style = Theme.body, color = Theme.text2, modifier = Modifier.weight(1f))
        if (retry != null) MAButton("Try again", retry, kind = ButtonKind.Ghost)
    }
}

/** True when the system's "remove animations" setting is on. */
@Composable
fun rememberReduceMotion(): Boolean {
    val context = LocalContext.current
    return remember {
        Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    }
}

/** A placeholder block that shimmers - still when animations are off. */
@Composable
fun Skeleton(modifier: Modifier = Modifier, height: Dp = Theme.rowMin) {
    val still = rememberReduceMotion()
    val lit = if (still) 0f else {
        val transition = rememberInfiniteTransition(label = "skeleton")
        val value by transition.animateFloat(0f, 1f, infiniteRepeatable(tween(900), RepeatMode.Reverse), label = "lit")
        value
    }
    val colour = Color(
        red = Theme.surface.red + (Theme.surface2.red - Theme.surface.red) * lit,
        green = Theme.surface.green + (Theme.surface2.green - Theme.surface.green) * lit,
        blue = Theme.surface.blue + (Theme.surface2.blue - Theme.surface.blue) * lit,
    )
    Box(modifier.fillMaxWidth().height(height).background(colour, RoundedCornerShape(Theme.radius)))
}

/** A screen's large title, left-aligned, with one optional trailing action. */
@Composable
fun ScreenTitle(title: String, modifier: Modifier = Modifier, trailing: (@Composable () -> Unit)? = null) {
    Row(modifier.fillMaxWidth().heightIn(min = Theme.touch), verticalAlignment = Alignment.CenterVertically) {
        Text(title, style = Theme.titleLG, color = Theme.text, modifier = Modifier.weight(1f).semantics { heading() })
        trailing?.invoke()
    }
}
