import fs from 'fs';
import { execSync } from 'child_process';
import { buildWorkerCode } from './public/shared.js';

const mockBatchConfig = {
    batch_id: "test_batch_123",
    created_at: new Date().toISOString(),
    ai_api_key: "nvapi-test",
    jobs: [
        {
            job_id: "job_0",
            uid: "user_123",
            title: "8 signs someone is secretly jealous of you.",
            script: "",
            voice: "en-US-GuyNeural",
            tts_engine: "edge",
            aspect_ratio: "9:16",
            target_duration: "45 seconds",
            enable_gpu: true
        }
    ]
};

const code = buildWorkerCode(mockBatchConfig, "hf_token_mock", "pexels_key_mock");
fs.writeFileSync('scratch_worker_test.py', code, 'utf8');

console.log("Written scratch_worker_test.py. Testing with python -m py_compile...");
try {
    const out = execSync('python -m py_compile scratch_worker_test.py');
    console.log("✅ PYTHON COMPILE SUCCESS! ZERO SYNTAX ERRORS.");
} catch (e) {
    console.error("❌ PYTHON COMPILE FAILED:", e.message);
    if (e.stderr) console.error(e.stderr.toString());
}
