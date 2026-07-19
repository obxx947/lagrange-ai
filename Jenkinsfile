// ============================================================
// 拉格朗日AI — Jenkins Pipeline
// ============================================================

pipeline {
    agent any
    
    environment {
        PYTHON_VERSION = '3.12'
        PROJECT_DIR = '拉格朗日智能体'
    }
    
    stages {
        stage('检出代码') {
            steps {
                checkout scm
                echo "拉格朗日AI — Jenkins CI/CD"
            }
        }
        
        stage('安装依赖') {
            steps {
                sh 'pip install -r requirements.txt'
                sh 'pip install pytest pytest-cov flake8'
            }
        }
        
        stage('代码检查') {
            parallel {
                stage('Python语法') {
                    steps {
                        sh 'python -m py_compile *.py'
                    }
                }
                stage('代码规范') {
                    steps {
                        sh 'flake8 *.py --max-line-length=120 --ignore=E203,W503 || true'
                    }
                }
                stage('配置验证') {
                    steps {
                        sh 'python config_loader.py'
                    }
                }
            }
        }
        
        stage('自动化测试') {
            steps {
                sh 'pytest test_api.py -v --tb=short --cov=. --cov-report=xml --junitxml=test-results.xml'
            }
            post {
                always {
                    junit 'test-results.xml'
                    publishCoverage(adapters: [coberturaAdapter('coverage.xml')])
                }
            }
        }
        
        stage('舰船数据验证') {
            steps {
                sh '''
                    python -c "
import json
d = json.load(open('lagrange_docs/ship_database.json'))
print(f'舰船数: {len(d)}')
assert len(d) >= 20
                    "
                '''
            }
        }
    }
    
    post {
        success {
            echo '✅ 构建成功！拉格朗日AI 所有检查通过'
        }
        failure {
            echo '❌ 构建失败！请检查日志'
        }
    }
}
