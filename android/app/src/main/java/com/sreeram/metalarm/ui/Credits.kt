// Who drew each exercise figure, and whose words the how-to steps are. A
// condition of using licensed material, not a courtesy. The twin of iOS
// CreditsView.

package com.sreeram.metalarm.ui

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.sreeram.metalarm.api.ExerciseCard
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.ErrorState
import com.sreeram.metalarm.theme.ListRow
import com.sreeram.metalarm.theme.RowGroup
import com.sreeram.metalarm.theme.Screen
import com.sreeram.metalarm.theme.SectionBlock
import com.sreeram.metalarm.theme.Theme

@Composable
fun CreditsScreen(model: AppModel, onBack: () -> Unit) {
    val context = LocalContext.current
    var cards by remember { mutableStateOf<List<ExerciseCard>>(emptyList()) }
    var error by remember { mutableStateOf("") }
    LaunchedEffect(Unit) {
        runCatching {
            val all = mutableListOf<ExerciseCard>()
            var cursor: String? = null
            do {
                val page = model.api.browseExercises("", null, null, cursor)
                all += page.items.filter { !it.isCustom }
                cursor = page.nextCursor
            } while (cursor != null)
            cards = all
        }.onFailure { if (it is kotlinx.coroutines.CancellationException) throw it else error = it.message.orEmpty() }
    }
    Screen {
        TopBar("Credits", onBack)
        Text(
            "MetalArm's own muscle figures are released under CC0 1.0. Many how-to steps come from the wger project (wger.de) and its contributors, under Creative Commons Attribution-ShareAlike licences.",
            style = Theme.body, color = Theme.text2,
        )
        ErrorState(error)
        val figures = cards.filter { it.mediaLicense != null && it.mediaAuthor != "MetalArm" }
        if (figures.isNotEmpty()) SectionBlock("Exercise figures") {
            RowGroup {
                figures.forEach { c ->
                    row {
                        ListRow(c.name, subtitle = "${c.mediaAuthor.orEmpty()} · ${c.mediaLicense.orEmpty()}", chevron = c.mediaSourceUrl != null,
                            onClick = c.mediaSourceUrl?.let { url -> { openLink(context, url) } })
                    }
                }
            }
        }
        val texts = cards.filter { it.textSourceUrl != null }
        if (texts.isNotEmpty()) SectionBlock("How-to steps") {
            RowGroup {
                texts.forEach { c ->
                    row {
                        ListRow(c.name, subtitle = "wger contributors · ${c.textLicense.orEmpty()}", chevron = true,
                            onClick = { openLink(context, c.textSourceUrl.orEmpty()) })
                    }
                }
            }
        }
    }
}
