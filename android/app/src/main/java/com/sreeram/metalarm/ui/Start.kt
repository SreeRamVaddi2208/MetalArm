// The way in: onboarding, sign-in / sign-up, and the training-path question -
// the twins of the iOS OnboardingView, AuthView and TrainingPathView.

package com.sreeram.metalarm.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.outlined.Circle
import androidx.compose.material.icons.outlined.FitnessCenter
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.sreeram.metalarm.BuildConfig
import com.sreeram.metalarm.R
import com.sreeram.metalarm.api.TrainingPath
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.ButtonKind
import com.sreeram.metalarm.theme.ErrorState
import com.sreeram.metalarm.theme.MAButton
import com.sreeram.metalarm.theme.Screen
import com.sreeram.metalarm.theme.Theme
import kotlinx.coroutines.launch

/** The first screen: what MetalArm is, and the way in. Calm - no glow. */
@Composable
fun OnboardingScreen(onFinish: (signUp: Boolean) -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .background(Theme.bg)
            .windowInsetsPadding(WindowInsets.systemBars)
            .padding(horizontal = Theme.gutter)
            .padding(bottom = Theme.Space.s24),
        verticalArrangement = Arrangement.spacedBy(Theme.Space.s24),
    ) {
        Spacer(Modifier.weight(1f))
        Box(
            Modifier.size(Theme.Space.s48 * 2).background(Theme.accentSoft, RoundedCornerShape(Theme.radiusSheet)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Filled.Bolt, contentDescription = null, tint = Theme.accent, modifier = Modifier.size(Theme.Space.s48))
        }
        Text("Every rep counts.\nLiterally.", style = Theme.titleLG, color = Theme.text, modifier = Modifier.testTag("onboardingTitle"))
        Text(
            "Log your workouts, level up your character, and compete with friends in your party.",
            style = Theme.body, color = Theme.text2,
        )
        Spacer(Modifier.weight(1f))
        Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
            MAButton("Get started", { onFinish(true) }, Modifier.testTag("getStartedButton"))
            MAButton("I already have an account", { onFinish(false) }, Modifier.testTag("haveAccountButton"), kind = ButtonKind.Secondary)
        }
    }
}

/** Create an account or sign in. Tokens go to the Keystore. */
@Composable
fun AuthScreen(model: AppModel, signUp: Boolean, onToggle: () -> Unit) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var displayName by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    val canSubmit = email.contains("@") && password.length >= (if (signUp) 8 else 1) && (!signUp || displayName.isNotBlank())

    // The submit button is the pinned primary, so it rides above the keyboard.
    Screen(
        pinned = {
            MAButton(
                if (model.isBusy) "…" else if (signUp) "Create account" else "Sign in",
                {
                    scope.launch {
                        if (signUp) model.signUp(email, password, displayName) else model.signIn(email, password)
                    }
                },
                Modifier.testTag("authSubmitButton"),
                enabled = canSubmit && !model.isBusy,
            )
        },
    ) {
        Spacer(Modifier.height(Theme.Space.s24))
        Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
            Text(if (signUp) "Create your account" else "Welcome back", style = Theme.titleLG, color = Theme.text)
            Text(
                if (signUp) "Your workouts, XP and records, synced to every device." else "Sign in to pick up where you left off.",
                style = Theme.body, color = Theme.text2,
            )
            if (signUp) Field(displayName, { displayName = it }, "Display name", "displayNameField")
            Field(email, { email = it }, "Email", "emailField", keyboard = KeyboardType.Email)
            Field(password, { password = it }, "Password", "passwordField", secure = true)
            if (signUp) Text("At least 8 characters.", style = Theme.caption, color = Theme.text2)
            ErrorState(model.errorMessage)
            MAButton(
                if (signUp) "Already have an account? Sign in" else "New to MetalArm? Create an account",
                {
                    onToggle()
                    model.errorMessage = ""
                },
                Modifier.testTag("authModeToggle"),
                kind = ButtonKind.Ghost, full = true,
            )
            Box(
                Modifier
                    .fillMaxWidth()
                    .heightIn(min = Theme.touch)
                    .clickable(role = Role.Button) { openLink(context, BuildConfig.WEB_BASE_URL + "/privacy") },
                contentAlignment = Alignment.Center,
            ) {
                Text("Privacy policy", style = Theme.caption, color = Theme.text2)
            }
        }
    }
}

/** Asked once after sign-up, and changeable from Profile: how you train. It
 *  shapes suggestions and never a score. */
@Composable
fun TrainingPathScreen(model: AppModel, isOnboarding: Boolean, onDone: () -> Unit) {
    val scope = rememberCoroutineScope()
    var chosen by rememberSaveable { mutableStateOf<String?>(null) }
    val paths = model.trainingPaths.ifEmpty { TrainingPath.fallbacks }

    LaunchedEffect(Unit) {
        // Seed from the saved path first, and never over a tap: the cards
        // render from the fallbacks straight away.
        if (chosen == null) chosen = model.me?.characterClass?.takeIf { it.isNotEmpty() }
        model.loadTrainingPaths()
    }

    Screen(
        top = isOnboarding,
        pinned = {
            Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s8), modifier = Modifier.windowInsetsPadding(WindowInsets.navigationBars)) {
                MAButton(
                    if (isOnboarding) "Start training" else "Save",
                    { scope.launch { chosen?.let { if (model.chooseTrainingPath(it)) onDone() } } },
                    Modifier.testTag("confirmPathButton"),
                    enabled = chosen != null && !model.isBusy,
                )
                if (isOnboarding) {
                    MAButton(
                        "Not sure yet",
                        {
                            // Recorded as asked-and-declined, so it doesn't come back.
                            scope.launch {
                                model.chooseTrainingPath("")
                                onDone()
                            }
                        },
                        Modifier.testTag("skipPathButton"),
                        kind = ButtonKind.Ghost, full = true,
                    )
                }
            }
        },
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s8), modifier = Modifier.padding(top = if (isOnboarding) Theme.Space.s32 else Theme.Space.s8)) {
            Text(if (isOnboarding) "Pick how you train" else "How you train", style = Theme.titleLG, color = Theme.text)
            Text(
                "It shapes the workouts and programs MetalArm leads with. It never changes your points or your rank.",
                style = Theme.body, color = Theme.text2,
            )
        }
        paths.forEach { path -> PathCard(path, selected = chosen == path.category) { chosen = path.category } }
        ErrorState(model.errorMessage)
    }
}

/** Selected: a 2 dp accent outline on accent-soft, and a check. No glow. */
@Composable
private fun PathCard(path: TrainingPath, selected: Boolean, onClick: () -> Unit) {
    val shape = RoundedCornerShape(Theme.radius)
    Row(
        Modifier
            .fillMaxWidth()
            .background(if (selected) Theme.accentSoft else Theme.surface, shape)
            .border(BorderStroke(if (selected) 2.dp else 1.dp, if (selected) Theme.accent else Theme.border), shape)
            .clickable(role = Role.RadioButton, onClick = onClick)
            .semantics(mergeDescendants = true) {
                this.selected = selected
                contentDescription = "${path.displayName} build. ${path.tagline} ${path.summary}"
            }
            .testTag("path-${path.category}")
            .padding(Theme.cardPadding),
        horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12),
    ) {
        PathCharacter(path.category, Modifier.width(104.dp).height(132.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
            Text(path.displayName, style = Theme.title, color = Theme.text)
            Text(path.tagline, style = Theme.body, color = Theme.text2)
            Text(path.summary, style = Theme.caption, color = Theme.text2)
        }
        Icon(
            if (selected) Icons.Filled.CheckCircle else Icons.Outlined.Circle,
            contentDescription = null,
            tint = if (selected) Theme.accent else Theme.border,
        )
    }
}

/** The path's figure: rendered from the iOS app's models (scripts/
 *  render_characters.swift), or a plain figure if no image exists. */
@Composable
fun PathCharacter(category: String, modifier: Modifier = Modifier) {
    val image = when (category) {
        "athlete" -> R.drawable.character_athlete
        "bodybuilder" -> R.drawable.character_bodybuilder
        "powerlifter" -> R.drawable.character_powerlifter
        else -> null
    }
    Box(modifier.background(Theme.surface2, RoundedCornerShape(Theme.radius)), contentAlignment = Alignment.Center) {
        if (image != null) {
            Image(painterResource(image), contentDescription = null, contentScale = ContentScale.Fit, modifier = Modifier.fillMaxSize().testTag("pathCharacter-$category"))
        } else {
            Icon(Icons.Outlined.FitnessCenter, contentDescription = null, tint = Theme.text2, modifier = Modifier.testTag("pathCharacterFallback-$category"))
        }
    }
}
