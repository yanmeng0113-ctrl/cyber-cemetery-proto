#!/bin/bash
set -eu
src="$(cd "$(dirname "$0")" && pwd)"
target="$RUNNER_TEMP/game-native-inputs"
mkdir -p "$target" safari-evidence/native-inputs
dest="$(pwd)/safari-evidence/native-inputs"
cd "$target"
cp "$src/NativeInputs.swift" .
cat > App.swift <<'SWIFT'
import UIKit
@main class Host: UIResponder, UIApplicationDelegate {}
SWIFT
# The runner's CocoaPods installation includes xcodeproj.
if ! ruby -rxcodeproj -e 'exit 0' 2>/dev/null; then
  pod_lib="$(brew --prefix cocoapods)/libexec"
  export GEM_HOME="$pod_lib"
  export GEM_PATH="$pod_lib"
  export PATH="$(brew --prefix ruby)/bin:$PATH"
fi
ruby -rxcodeproj - <<'RUBY'
project = Xcodeproj::Project.new('Inputs.xcodeproj')
host = project.new_target(:application, 'InputHost', :ios, '16.0')
suite = project.new_target(:ui_test_bundle, 'InputTests', :ios, '16.0')
suite.add_dependency(host)
[[host,'App.swift'],[suite,'NativeInputs.swift']].each do |target,file|
  target.source_build_phase.add_file_reference(project.main_group.new_file(file))
  target.build_configurations.each do |config|
    config.build_settings.merge!({'GENERATE_INFOPLIST_FILE'=>'YES','PRODUCT_BUNDLE_IDENTIFIER'=>"test.local."+target.name,'SWIFT_VERSION'=>'5.0','TARGETED_DEVICE_FAMILY'=>'1'})
    config.build_settings['TEST_TARGET_NAME']=host.name if target==suite
  end
end
project.save
scheme=Xcodeproj::XCScheme.new
scheme.add_build_target(host)
scheme.add_test_target(suite)
scheme.save_as('Inputs.xcodeproj','Inputs')
RUBY
set +e
xcodebuild -project Inputs.xcodeproj -scheme Inputs -destination "id=$SIM_UDID" -parallel-testing-enabled NO -derivedDataPath "$target/build" -resultBundlePath "$target/Inputs.xcresult" test > "$target/test.log" 2>&1
status=$?
set -e
tail -55 "$target/test.log"
grep -E 'Test Case|error:|Executed [0-9]+ tests' "$target/test.log" > "$dest/outcome.txt" || true
if [[ -d "$target/Inputs.xcresult" ]]; then
  xcrun xcresulttool export attachments --path "$target/Inputs.xcresult" --output-path "$dest" || true
fi
exit "$status"
