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
            VStack(alignment: .leading, spacing: 14) {
                Text(isSignUp ? "Create your account" : "Welcome back")
                    .font(Theme.display(30))
                    .foregroundStyle(Theme.text)
                Text(isSignUp ? "Your workouts, XP and records, synced to every device." : "Sign in to pick up where you left off.")
                    .font(Theme.body(15))
                    .foregroundStyle(Theme.dim)
                    .padding(.bottom, 8)

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
                SecureField("", text: $password, prompt: Text("Password").foregroundStyle(Theme.faint))
                    .textContentType(isSignUp ? .newPassword : .password)
                    .modifier(FieldStyle())
                    .accessibilityIdentifier("passwordField")
                if isSignUp {
                    Text("At least 8 characters.")
                        .font(Theme.body(12))
                        .foregroundStyle(Theme.faint)
                }

                ErrorText(message: model.errorMessage)

                Button {
                    Task { await submit() }
                } label: {
                    if model.isBusy {
                        ProgressView().tint(Theme.bg)
                    } else {
                        Text(isSignUp ? "Create Account" : "Sign In")
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(!canSubmit || model.isBusy)
                .opacity(canSubmit ? 1 : 0.5)
                .accessibilityIdentifier("authSubmitButton")
                .padding(.top, 6)

                Button(isSignUp ? "Already have an account? Sign in" : "New to MetalArm? Create an account") {
                    mode = isSignUp ? .signIn : .signUp
                    model.errorMessage = ""
                }
                .font(Theme.body(14, .semibold))
                .foregroundStyle(Theme.fire)
                .frame(maxWidth: .infinity)
                .accessibilityIdentifier("authModeToggle")

                Link("Privacy Policy", destination: AppConfig.privacyPolicyURL)
                    .font(Theme.body(12))
                    .foregroundStyle(Theme.dim)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 12)
            }
            .padding(24)
            .padding(.top, 40)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Theme.bg.ignoresSafeArea())
    }

    private func field(_ title: String, text: Binding<String>) -> some View {
        TextField("", text: text, prompt: Text(title).foregroundStyle(Theme.faint))
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
            .font(Theme.body(16))
            .foregroundStyle(Theme.text)
            .padding(14)
            .background(Theme.card, in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.cardBorder))
    }
}

#Preview {
    AuthView(mode: .constant(.signUp))
        .environment(AppModel(api: MockAPIClient(signedIn: false)))
        .preferredColorScheme(.dark)
}
