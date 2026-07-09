# Tree-0.1 · turn 6 · inspect_context

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:32:50.743Z -->

**Intent:** `inspect_context`  
**Payload:** `call_site_options`

---

Let me check the latest workspace view to see if the probe for `inline PRPc.PseudoRP.fi.` was accepted or rejected.

So `inline PRPc.PseudoRP.fi.` was also rejected. Hmm. Let me think about why `inline` is being rejected. In phoare mode, `inline` might require a different syntax. Let me look up the call site options to understand the procedure structure.

Actually, maybe the issue is that in EasyCrypt, within phoare mode after `proc`, `inline` might not work in the same way. Let me look at the call site options to get more info.

Actually, wait - I just realized: this is a `phoare` judgment (one-sided), so there's no `{1}` or `{2}` side specification. 

Maybe I need to try a different tactic altogether. Let me attempt `sp.` to simplify some assignments, or `wp.` to work backwards from the end. Or I could check what the call_site_options documentation says about the procedures involved.
