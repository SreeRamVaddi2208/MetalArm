//
//  AuthView.swift
//  MetalARM
//
//  Create an account or sign in. Tokens go to the Keychain (TokenStore).
//

import SwiftUI

struct AuthView: View {
    enum Mode {
        case signUp, signIn
    }

    @Environment(AppModel.self) private var model
    @Binding var mode: Mode
    @State private var displayName = ""
    @State private var email = ""
    @State private var password = ""

    private var isSignUp: Bool { mode == .signUp }

    private var canSubmit: Bool {
        email.contains("@") && password.count >= (isSignUp ? 8 : 1) && (!isSignUp || !displayName.trimmed.isEmpty)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s16) {
                Text(isSignUp ? "Create your account" : "Welcome back")
                    .font(Theme.titleLG)
                    .foregroundStyle(Theme.text)
                Text(isSignUp ? "Your workouts, XP and records, synced to every device." : "Sign in to pick up where you left off.")
                    .font(Theme.body)
                    .foregroundStyle(Theme.text2)

                if isSignUp {
                    field("Display name", text: $displayName)
                        .textContentType(.nickname)
                        .accessibilityIdentifier("displayNameField")
                }
                field("Email", text: $email)
                    .keyboardType(.emailAddress)
                    .textContentType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .accessibilityIdentifier("emailField")
                SecureField("", text: $password, prompt: Text("Password").foregroundStyle(Theme.text3))
                    .textContentType(isSignUp ? .newPassword : .password)
                    .modifier(FieldStyle())
                    .accessibilityIdentifier("passwordField")
                if isSignUp {
                    Text("At least 8 characters.")
                        .font(Theme.caption)
                        .foregroundStyle(Theme.text2)
                }

                ErrorText(message: model.errorMessage)

                Button {
                    Task { await submit() }
                } label: {
                    if model.isBusy {
                        ProgressView().tint(Theme.onAccent)
                    } else {
                        Text(isSignUp ? "Create account" : "Sign in")
                    }
                }
                .buttonStyle(.primary)
                .disabled(!canSubmit || model.isBusy)
                .accessibilityIdentifier("authSubmitButton")

                Button(isSignUp ? "Already have an account? Sign in" : "New to MetalArm? Create an account") {
                    mode = isSignUp ? .signIn : .signUp
                    model.errorMessage = ""
                }
                .buttonStyle(MAButtonStyle(kind: .ghost))
                .accessibilityIdentifier("authModeToggle")

                Link("Privacy policy", destination: AppConfig.privacyPolicyURL)
                    .font(Theme.caption)
                    .foregroundStyle(Theme.text2)
                    .frame(maxWidth: .infinity, minHeight: Theme.touch)
            }
            .screen()
            .padding(.top, Theme.Space.s48)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Theme.bg.ignoresSafeArea())
    }

    private func field(_ title: String, text: Binding<String>) -> some View {
        TextField("", text: text, prompt: Text(title).foregroundStyle(Theme.text3))
            .modifier(FieldStyle())
    }

    private func submit() async {
        if isSignUp {
            await model.signUp(email: email, password: password, displayName: displayName)
        } else {
            await model.signIn(email: email, password: password)
        }
    }
}

struct FieldStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(Theme.body)
            .foregroundStyle(Theme.text)
            .padding(.horizontal, Theme.Space.s16)
            .frame(minHeight: Theme.buttonHeight)
            .background(Theme.surface2, in: RoundedRectangle(cornerRadius: Theme.radius))
    }
}

#Preview {
    AuthView(mode: .constant(.signUp))
        .environment(AppModel(api: MockAPIClient(signedIn: false)))
        .preferredColorScheme(.dark)
}
