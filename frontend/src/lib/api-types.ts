// AUTO-GENERATED from the backend OpenAPI schema by scripts/gen-api-types.mjs.
// Do not edit by hand; run `npm run gen:types` to refresh.

export interface paths {
    "/api/tenants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Signup */
        post: operations["signup_api_tenants_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tenants/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_tenants_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/login-code": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login Code */
        post: operations["login_code_api_auth_login_code_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/verify-code": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Code */
        post: operations["verify_code_api_auth_verify_code_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/dev-login-code": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Dev Login Code
         * @description Local-dev only: return the last issued code for ``email``.
         *
         *     Backs the demo's captured-code path and the E2E login-in-chat flow. Gated to
         *     the local environment so a real deployment can never expose codes.
         */
        get: operations["dev_login_code_api_auth_dev_login_code_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/platform/ping": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ping */
        get: operations["ping_api_platform_ping_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/platform/metrics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Metrics */
        get: operations["get_metrics_api_platform_metrics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/platform/tenants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tenants */
        get: operations["list_tenants_api_platform_tenants_get"];
        put?: never;
        /** Provision Tenant */
        post: operations["provision_tenant_api_platform_tenants_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/platform/tenants/slug-availability": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Check Slug Availability */
        get: operations["check_slug_availability_api_platform_tenants_slug_availability_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/platform/tenants/{tenant_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Tenant Status */
        patch: operations["update_tenant_status_api_platform_tenants__tenant_id__patch"];
        trace?: never;
    };
    "/api/public/tenant/{slug}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Resolve Tenant */
        get: operations["resolve_tenant_api_public_tenant__slug__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/onboarding/state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get State */
        get: operations["get_state_api_onboarding_state_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/onboarding/message": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Message */
        post: operations["post_message_api_onboarding_message_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/onboarding/message/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Message Stream */
        post: operations["post_message_stream_api_onboarding_message_stream_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/onboarding/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Confirm */
        post: operations["confirm_api_onboarding_confirm_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Documents */
        get: operations["list_documents_api_knowledge_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/upload": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload Document */
        post: operations["upload_document_api_knowledge_upload_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/{document_id}/reprocess": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reprocess Document */
        post: operations["reprocess_document_api_knowledge__document_id__reprocess_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/urls": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ingest Url */
        post: operations["ingest_url_api_knowledge_urls_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/records": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Records
         * @description Everything the assistant knows, as readable sections.
         */
        get: operations["list_records_api_knowledge_records_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/drafts/upload": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Draft From Upload
         * @description Read a file and return it as sections to review. Nothing is embedded yet -
         *     a draft answers no customer question until it is saved.
         */
        post: operations["draft_from_upload_api_knowledge_drafts_upload_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/drafts/url": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Draft From Url
         * @description Read a page and return it as sections to review (see /drafts/upload).
         */
        post: operations["draft_from_url_api_knowledge_drafts_url_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/records/{document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Record */
        get: operations["get_record_api_knowledge_records__document_id__get"];
        /**
         * Save Record
         * @description Save the owner's reviewed sections and make them answerable.
         */
        put: operations["save_record_api_knowledge_records__document_id__put"];
        post?: never;
        /** Delete Record */
        delete: operations["delete_record_api_knowledge_records__document_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/chat": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Chat */
        post: operations["chat_api_chat_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/chat/{conversation_id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Conversation Messages
         * @description T-031: unauthenticated transcript poll for the customer surface - the
         *     only way a resolved escalation's human_agent reply reaches an
         *     already-open customer tab (no push/websocket mechanism exists anywhere
         *     in this codebase). Trust model matches POST /api/chat's conversation_id:
         *     knowing the UUID is the capability, same as the rest of this bare
         *     customer surface (no login).
         *
         *     ``after`` lets a client that already has the transcript up to some
         *     timestamp poll for only what's new, rather than re-fetching the whole
         *     history on every 5s tick.
         */
        get: operations["get_conversation_messages_api_chat__conversation_id__messages_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/conversations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Conversations */
        get: operations["list_conversations_api_conversations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/conversations/{conversation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Conversation */
        get: operations["get_conversation_api_conversations__conversation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/escalations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Escalations */
        get: operations["list_escalations_api_escalations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/escalations/{escalation_id}/claim": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Claim Escalation */
        post: operations["claim_escalation_api_escalations__escalation_id__claim_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/escalations/{escalation_id}/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resolve Escalation */
        post: operations["resolve_escalation_api_escalations__escalation_id__resolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pricing/rules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Pricing Rules */
        get: operations["list_pricing_rules_api_pricing_rules_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pricing/rules/{rule_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Pricing Rule */
        patch: operations["update_pricing_rule_api_pricing_rules__rule_id__patch"];
        trace?: never;
    };
    "/api/pricing/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Catalog Items */
        get: operations["list_catalog_items_api_pricing_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/dashboards/costs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Cost Dashboard */
        get: operations["get_cost_dashboard_api_dashboards_costs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/dashboards/evals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Eval Dashboard */
        get: operations["get_eval_dashboard_api_dashboards_evals_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health
         * @description Readiness probe (the ALB target-group health check). Pings the DB so an
         *     instance that can't reach Postgres is pulled from rotation instead of
         *     serving 500s.
         */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** Body_draft_from_upload_api_knowledge_drafts_upload_post */
        Body_draft_from_upload_api_knowledge_drafts_upload_post: {
            /** File */
            file: string;
        };
        /** Body_upload_document_api_knowledge_upload_post */
        Body_upload_document_api_knowledge_upload_post: {
            /** File */
            file: string;
            /** Doc Type */
            doc_type: string;
        };
        /**
         * BudgetUsage
         * @description Where this month's spend sits against the standing testing budget (P-1).
         *     ``fraction`` is None when no budget is configured.
         */
        BudgetUsage: {
            /** Fraction */
            fraction: number | null;
            /** Warning */
            warning: boolean;
        };
        /** CatalogItemResponse */
        CatalogItemResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Price Cents */
            price_cents: number | null;
            /** Active */
            active: boolean;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** ChatRequest */
        ChatRequest: {
            /** Slug */
            slug: string;
            /** Conversation Id */
            conversation_id?: string | null;
            /** Message */
            message: string;
        };
        /** ChipSpec */
        ChipSpec: {
            /** Label */
            label: string;
            /** Value */
            value: string;
            /**
             * Dashed
             * @default false
             */
            dashed: boolean;
        };
        /** ConversationDetail */
        ConversationDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Customer Ref */
            customer_ref: string | null;
            /** Channel */
            channel: string;
            /** Status */
            status: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Total Cost Usd */
            total_cost_usd: number;
            /** Messages */
            messages: components["schemas"]["MessageDetail"][];
        };
        /** ConversationSummary */
        ConversationSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Customer Ref */
            customer_ref: string | null;
            /** Status */
            status: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Message Count */
            message_count: number;
        };
        /** CostDashboard */
        CostDashboard: {
            /** Cost Today Usd */
            cost_today_usd: number;
            /** Cost Yesterday Usd */
            cost_yesterday_usd: number;
            /** Cost This Month Usd */
            cost_this_month_usd: number;
            /** Cost Prev Month Usd */
            cost_prev_month_usd: number;
            /** Avg Cost Per Conversation Usd */
            avg_cost_per_conversation_usd: number | null;
            /** Conversation Count */
            conversation_count: number;
            /** Escalated Conversation Count */
            escalated_conversation_count: number;
            /** Escalation Rate */
            escalation_rate: number | null;
            /** Daily Costs */
            daily_costs: components["schemas"]["DailyCost"][];
            /** Monthly Budget Usd */
            monthly_budget_usd: number;
            monthly_budget_used: components["schemas"]["BudgetUsage"];
        };
        /** DailyCost */
        DailyCost: {
            /**
             * Day
             * Format: date
             */
            day: string;
            /** Cost Usd */
            cost_usd: number;
        };
        /** DocumentResponse */
        DocumentResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Filename */
            filename: string;
            /** Doc Type */
            doc_type: string;
            /** Status */
            status: string;
            /** Error */
            error: string | null;
        };
        /** EscalationResponse */
        EscalationResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /** Reason */
            reason: string;
            /** Status */
            status: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Resolved At */
            resolved_at: string | null;
        };
        /** EvalCheck */
        EvalCheck: {
            /** Metric */
            metric: string;
            /** Value */
            value: number | null;
            /** Threshold */
            threshold: number;
            /** Passed */
            passed: boolean;
        };
        /** EvalDashboard */
        EvalDashboard: {
            /** Runs */
            runs: components["schemas"]["EvalRunSummary"][];
        };
        /** EvalRunSummary */
        EvalRunSummary: {
            /** Run Type */
            run_type: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Git Sha */
            git_sha: string;
            /** Metrics */
            metrics: {
                [key: string]: unknown;
            };
            /** Checks */
            checks: components["schemas"]["EvalCheck"][];
            /** Passed */
            passed: boolean;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** InputSpec */
        InputSpec: {
            /**
             * Kind
             * @default text
             * @enum {string}
             */
            kind: "text" | "chips" | "masked" | "cta";
            /**
             * Placeholder
             * @default
             */
            placeholder: string;
            /** Chips */
            chips?: components["schemas"]["ChipSpec"][];
            /** Mask */
            mask?: string | null;
            /** Cta Label */
            cta_label?: string | null;
        };
        /**
         * KnowledgeRecord
         * @description A document as the knowledge screen reads it - the row plus its sections.
         */
        KnowledgeRecord: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Filename */
            filename: string;
            /** Doc Type */
            doc_type: string;
            /** Status */
            status: string;
            /** Error */
            error: string | null;
            /** Sections */
            sections: components["schemas"]["Section"][];
        };
        /**
         * LoginCodeRequest
         * @description Raw typed text, not a validated address - see ``_resolve_email``.
         */
        LoginCodeRequest: {
            /** Email */
            email: string;
        };
        /**
         * LoginCodeResponse
         * @description The address the code was actually sent to, after normalization.
         *
         *     The owner may have typed a sentence, or odd casing; echoing the resolved
         *     address back is what lets the thread say where to look for the code without
         *     the client having to re-derive it (and risk disagreeing with the server).
         */
        LoginCodeResponse: {
            /** Email */
            email: string;
        };
        /** MessageDetail */
        MessageDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Role */
            role: string;
            /** Content */
            content: string;
            /** Agent Node */
            agent_node: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Metadata */
            metadata: {
                [key: string]: unknown;
            };
            /** Cost Usd */
            cost_usd: number | null;
            /** Tool Calls */
            tool_calls: components["schemas"]["ToolCallDetail"][];
        };
        /** OnboardingConfirmResponse */
        OnboardingConfirmResponse: {
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
        };
        /** OnboardingMessageRequest */
        OnboardingMessageRequest: {
            /** Text */
            text?: string | null;
            selection?: components["schemas"]["SelectionPayload"] | null;
        };
        /** OnboardingStateResponse */
        OnboardingStateResponse: {
            /** Stage */
            stage: string;
            /** Prompt */
            prompt: string;
            /** Draft */
            draft: {
                [key: string]: string;
            };
            /** Completed */
            completed: boolean;
            /** History */
            history: {
                [key: string]: string;
            }[];
            input: components["schemas"]["InputSpec"] | null;
            /** Can Confirm */
            can_confirm: boolean;
        };
        /** PlatformMetrics */
        PlatformMetrics: {
            /** Tenant Count */
            tenant_count: number;
            /** Total Cost Usd */
            total_cost_usd: number;
        };
        /** PricingRuleResponse */
        PricingRuleResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            /** Label */
            label: string;
            /** Unit Amount Cents */
            unit_amount_cents: number;
            /** Unit */
            unit: string;
            /** Active */
            active: boolean;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** PricingRuleUpdate */
        PricingRuleUpdate: {
            /** Code */
            code?: string | null;
            /** Label */
            label?: string | null;
            /** Unit Amount Dollars */
            unit_amount_dollars?: number | string | null;
            /** Unit */
            unit?: string | null;
            /** Active */
            active?: boolean | null;
        };
        /** ProvisionTenantRequest */
        ProvisionTenantRequest: {
            /** Slug */
            slug: string;
            /** Name */
            name: string;
        };
        /** ProvisionTenantResponse */
        ProvisionTenantResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Slug */
            slug: string;
            /** Name */
            name: string;
            /** Status */
            status: string;
            /** Note */
            note: string;
        };
        /** PublicMessage */
        PublicMessage: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Role */
            role: string;
            /** Content */
            content: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** ResolveRequest */
        ResolveRequest: {
            /** Message */
            message?: string | null;
        };
        /** SaveRecordRequest */
        SaveRecordRequest: {
            /** Sections */
            sections: components["schemas"]["Section"][];
        };
        /**
         * Section
         * @description One readable block of a document: a fixed heading and the owner's text.
         */
        Section: {
            /** Heading */
            heading: string;
            /** Body */
            body: string;
        };
        /** SelectionPayload */
        SelectionPayload: {
            /** Beat */
            beat: string;
            /** Values */
            values?: string[];
        };
        /** SlugAvailabilityResponse */
        SlugAvailabilityResponse: {
            /** Available */
            available: boolean;
        };
        /** TenantMeResponse */
        TenantMeResponse: {
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /** Slug */
            slug: string;
            /** Name */
            name: string;
            /** Brand */
            brand?: {
                [key: string]: unknown;
            };
        };
        /** TenantResolveResponse */
        TenantResolveResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Status */
            status: string;
            /** Brand */
            brand: {
                [key: string]: unknown;
            };
            /** Customer */
            customer: {
                [key: string]: unknown;
            };
        };
        /** TenantSignupRequest */
        TenantSignupRequest: {
            /** Slug */
            slug: string;
            /** Name */
            name: string;
        };
        /** TenantSignupResponse */
        TenantSignupResponse: {
            /**
             * Tenant Id
             * Format: uuid
             */
            tenant_id: string;
            /** Slug */
            slug: string;
        };
        /** TenantSummary */
        TenantSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Slug */
            slug: string;
            /** Name */
            name: string;
            /** Status */
            status: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Conversation Count */
            conversation_count: number;
            /** Cost Usd */
            cost_usd: number;
        };
        /** ToolCallDetail */
        ToolCallDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Tool Name */
            tool_name: string;
            /** Arguments */
            arguments: {
                [key: string]: unknown;
            };
            /** Result */
            result: unknown;
            /** Success */
            success: boolean;
            /** Latency Ms */
            latency_ms: number | null;
        };
        /** UpdateTenantStatusRequest */
        UpdateTenantStatusRequest: {
            /** Status */
            status: string;
        };
        /** UrlIngestRequest */
        UrlIngestRequest: {
            /** Url */
            url: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** VerifyCodeRequest */
        VerifyCodeRequest: {
            /** Email */
            email: string;
            /** Code */
            code: string;
        };
        /** VerifyCodeResponse */
        VerifyCodeResponse: {
            /** Access Token */
            access_token: string;
            /** User Id */
            user_id: string;
            /** Tenant Id */
            tenant_id: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    signup_api_tenants_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TenantSignupRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TenantSignupResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    me_api_tenants_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TenantMeResponse"];
                };
            };
        };
    };
    login_code_api_auth_login_code_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginCodeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoginCodeResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_code_api_auth_verify_code_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VerifyCodeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VerifyCodeResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    dev_login_code_api_auth_dev_login_code_get: {
        parameters: {
            query: {
                email: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ping_api_platform_ping_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: boolean;
                    };
                };
            };
        };
    };
    get_metrics_api_platform_metrics_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlatformMetrics"];
                };
            };
        };
    };
    list_tenants_api_platform_tenants_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TenantSummary"][];
                };
            };
        };
    };
    provision_tenant_api_platform_tenants_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProvisionTenantRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProvisionTenantResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    check_slug_availability_api_platform_tenants_slug_availability_get: {
        parameters: {
            query: {
                slug: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SlugAvailabilityResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_tenant_status_api_platform_tenants__tenant_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tenant_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateTenantStatusRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TenantSummary"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_tenant_api_public_tenant__slug__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TenantResolveResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_state_api_onboarding_state_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OnboardingStateResponse"];
                };
            };
        };
    };
    post_message_api_onboarding_message_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OnboardingMessageRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OnboardingStateResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    post_message_stream_api_onboarding_message_stream_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OnboardingMessageRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    confirm_api_onboarding_confirm_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OnboardingConfirmResponse"];
                };
            };
        };
    };
    list_documents_api_knowledge_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentResponse"][];
                };
            };
        };
    };
    upload_document_api_knowledge_upload_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_document_api_knowledge_upload_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reprocess_document_api_knowledge__document_id__reprocess_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ingest_url_api_knowledge_urls_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UrlIngestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_records_api_knowledge_records_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeRecord"][];
                };
            };
        };
    };
    draft_from_upload_api_knowledge_drafts_upload_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_draft_from_upload_api_knowledge_drafts_upload_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeRecord"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    draft_from_url_api_knowledge_drafts_url_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UrlIngestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeRecord"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_record_api_knowledge_records__document_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeRecord"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    save_record_api_knowledge_records__document_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveRecordRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeRecord"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_record_api_knowledge_records__document_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    chat_api_chat_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChatRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversation_messages_api_chat__conversation_id__messages_get: {
        parameters: {
            query: {
                slug: string;
                after?: string | null;
                limit?: number;
            };
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicMessage"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_conversations_api_conversations_get: {
        parameters: {
            query?: {
                status?: ("open" | "escalated" | "closed") | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationSummary"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversation_api_conversations__conversation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_escalations_api_escalations_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EscalationResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    claim_escalation_api_escalations__escalation_id__claim_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                escalation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EscalationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_escalation_api_escalations__escalation_id__resolve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                escalation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResolveRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EscalationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_pricing_rules_api_pricing_rules_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PricingRuleResponse"][];
                };
            };
        };
    };
    update_pricing_rule_api_pricing_rules__rule_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rule_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PricingRuleUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PricingRuleResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_catalog_items_api_pricing_catalog_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogItemResponse"][];
                };
            };
        };
    };
    get_cost_dashboard_api_dashboards_costs_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CostDashboard"];
                };
            };
        };
    };
    get_eval_dashboard_api_dashboards_evals_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvalDashboard"];
                };
            };
        };
    };
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
}
