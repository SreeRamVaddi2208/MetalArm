// Inputs and small shared pieces for the screens.

package com.sreeram.metalarm.ui

import android.content.Context
import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import com.sreeram.metalarm.theme.Theme

/** A text field on surface-2, 52 dp, with a placeholder prompt. */
@Composable
fun Field(
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    tag: String,
    modifier: Modifier = Modifier,
    keyboard: KeyboardType = KeyboardType.Text,
    secure: Boolean = false,
) {
    BasicTextField(
        value = value,
        onValueChange = onValueChange,
        singleLine = true,
        textStyle = Theme.body.copy(color = Theme.text),
        cursorBrush = SolidColor(Theme.accent),
        keyboardOptions = KeyboardOptions(keyboardType = if (secure) KeyboardType.Password else keyboard),
        visualTransformation = if (secure) PasswordVisualTransformation() else VisualTransformation.None,
        modifier = modifier.fillMaxWidth().testTag(tag),
        decorationBox = { inner ->
            Box(
                Modifier
                    .fillMaxWidth()
                    .heightIn(min = Theme.buttonHeight)
                    .background(Theme.surface2, RoundedCornerShape(Theme.radius))
                    .padding(horizontal = Theme.Space.s16),
                contentAlignment = Alignment.CenterStart,
            ) {
                if (value.isEmpty()) Text(placeholder, style = Theme.body, color = Theme.text3)
                inner()
            }
        },
    )
}

/** Privacy and Support open in a browser tab. */
fun openLink(context: Context, url: String) {
    CustomTabsIntent.Builder().build().launchUrl(context, Uri.parse(url))
}
