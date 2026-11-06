# 9. Questions to test yourself

Try each one before reading the answer.

## The model

**1. Why not choose the model with the best accuracy?**
It is 7 times larger and about 6 times slower for 2 points. Size and speed drive start time and cost, so the rule accepts a small accuracy loss. It was fixed before any results existed so that the choice could not be argued into shape afterwards.

**2. Test accuracy is 3.5 points above validation. What would you check first?**
A leak: do train and test share images? Here they share no names and 2 exact copies out of 25,250, which is too few to matter. The likely cause is that test images were reviewed by hand and training images, including validation, were not.

**3. The sweep beat the old score by 0.11 points. Is that model better?**
There is no evidence of that. Sampling alone can move a score on 7,575 images by about 0.73 points. The rule still takes it, because the rule was set first, but it should not be described as an improvement.

**4. Why is quantized ONNX not deployed, when it is 4 times smaller and twice as fast?**
It scores 85.76%, below the 87.05% floor. The rule that excluded smaller models excludes it too.

**5. Why can `fruity finalize` be run twice safely?**
`evals/final.json` acts as a lock. When it exists, the command rewrites the report from it and never opens the test set.

## The service

**6. Why does the service not need PyTorch?**
ONNX Runtime runs the exported calculation, and preprocessing is Pillow and NumPy. PyTorch is needed only to train and to export.

**7. Why is `threads` set to 1?**
ONNX Runtime counts the host's cores, not the container's share. Many threads on half a core fight each other.

**8. Why are the model endpoints plain functions and not `async`?**
FastAPI runs plain functions in a thread pool. Heavy work in an `async` function would block the event loop, and `/health` would stop answering.

**9. A file is named `photo.jpg` but holds text. What does the API answer, and why not a 500?**
422. It claims a valid type, then `read_image` fails to decode it and says so. A 500 would mean the server broke, which it did not.

## Infrastructure

**10. Why are there two Terraform folders?**
CI needs an identity and state storage before it can run. Bootstrap creates them by hand. Keeping the budget and kill switch there also keeps them out of reach of the deploy identity.

**11. What stops a stolen copy of this repo from deploying to Azure?**
There is no key to steal. Azure trusts only GitHub-signed tokens whose subject is this repo's `main` branch.

**12. Why does merging to `main` not deploy anything after teardown?**
Every deploy job needs `DEPLOY_ENABLED`, and it gets deleted at teardown. Without that, a typo fix would rebuild the service and restart the bill.

**13. Why does `.dockerignore` start with `*`?**
An exclude list lets new files in by default, including secrets and data. An allowlist keeps them out by default.

## Cost

**14. Why is the budget not the main cost control?**
It does not stop anything by itself, and it can act up to about two days late. In a 24-hour deployment, that is after everything has already happened.

**15. Why does the budget's trigger sit at half the limit?**
Because the data is late. Spending continues between the real moment and the moment the budget sees it, so it has to act early to stay under the limit.

**16. What is the most compute can cost in 24 hours? Work it out.**
1.25 vCPU and 2.5 GiB at full caps. That is 1.25 x 0.000024 + 2.5 x 0.000003 = USD 0.0000375 per second, or USD 0.135 per hour, or USD 3.24 over 24 hours, before the free grant.

**17. An empty `allowed_ip_ranges` looks harmless. Why is it refused?**
With no rules, Container Apps accepts everyone, so an empty list means the opposite of what it looks like.

## Measuring

**18. Why report p95 and not the average?**
An average hides the slow requests that people remember. It can also describe nobody's actual experience.

**19. Throughput falls from 10 to 20 users. What does that tell you?**
The service is past capacity. Requests queue and time goes on juggling. Latency will be rising fast too.

**20. Why raise the rate limit for the load test?**
Otherwise the test measures the limit: most requests get refused quickly, which looks like speed.

## Exercises

1. **Move the threshold.** Change `margin` in `compare.yaml` to 0.01, run `uv run fruity compare`, and read which model wins. Then undo it. Do not rerun `fruity finalize`.
2. **Break the export check.** In `finalize.py`, set `max_export_gap` to `-1` in a test, and watch it stop before the test set.
3. **Watch a limit work.** Run `docker compose up --build`, then run `uv run fruity loadtest --host http://127.0.0.1:8000 --output outputs/loadtest`. Compare it with a run after setting `FRUITY_REQUESTS_PER_MINUTE=100000`.
4. **Feel the size limits.** Run the API image with `--cpus 0.25 --memory 256m`, and find out what fails first.
5. **Add an alert.** Add a `RestartCount` alert to `monitoring.tf`, and check it with `terraform -chdir=infra validate`.
6. **Check the ceiling.** Change `max_replicas` to 5 and run `terraform -chdir=infra test`. See the test fail, and work out what the new ceiling would be.
