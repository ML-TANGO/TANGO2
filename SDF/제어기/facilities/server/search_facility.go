package server

import (
	"context"
	"fmt"
	"strings"

	"github.com/go-pg/pg/v10"
	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// SearchFacility - 설비 검색 API
func (s FacilitiesServer) SearchFacility(ctx context.Context, req *facilities.SearchFacilityRequest) (*facilities.SearchFacilityResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// 기본 쿼리
	query := facilityQuery(ctx, conn, true)
	query = query.WrapWith("list").Table("list")

	// 전체에서 검색
	if len(req.Search) > 0 {
		query.WhereGroup(func(q *pg.Query) (*pg.Query, error) {
			q.WhereOr(fmt.Sprintf("facility_name ILIKE '%%%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("site_id LIKE '%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("site_group->>'siteName' ILIKE '%%%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("group_id LIKE '%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("site_group->>'groupName' ILIKE '%%%s%%'", req.Search))

			q.WhereOr(fmt.Sprintf("product->>'productName' ILIKE '%%%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("manufacture_id LIKE '%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("model_number LIKE '%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("serial_number LIKE '%s%%'", req.Search))
			return q, nil
		})
	}

	// 사이트 ID 필터링
	if len(req.SiteId) > 0 {
		query.Where("site_id = ?", req.SiteId)
	}

	// 설비 그룹 필터링
	if len(req.GroupId) > 0 {
		query.Where("site_id = ?", req.SiteId)
		query.Where("group_id = ?", req.GroupId)
	}

	// 설비명으로 검색
	if len(req.Name) > 0 {
		query.Where(fmt.Sprintf("facility_name ILIKE '%%%s%%'", req.Name))
	}

	// 제조사로 필터링
	if len(req.ManufactureId) > 0 {
		query.WhereIn("manufacture_id IN (?)", req.ManufactureId)
	}

	// 모델 번호로 검색
	if len(req.Model) > 0 {
		query.Where(fmt.Sprintf("model_number ILIKE '%s%%'", req.Model))
	}

	// 일련 번호로 검색
	if len(req.Sn) > 0 {
		query.Where(fmt.Sprintf("serial_number ILIKE '%s%%'", req.Sn))
	}

	res := &facilities.SearchFacilityResponse{Link: make(map[string]string)}
	if req.Limit > 0 {
		count, err := query.Count()
		if err != nil {
			return nil, pgorm.GetError(ctx, err)
		} else if count == 0 {
			return res, nil
		} else {
			res.Count = uint64(count)
		}
	}

	// 정렬
	for _, order := range req.Order {
		var column string
		switch order {
		case facilities.SearchFacilityRequest_site_name_asc:
			column = "site_group->>'siteName'"
		case facilities.SearchFacilityRequest_site_name_desc:
			column = "site_group->>'siteName' DESC"
		case facilities.SearchFacilityRequest_group_name_asc:
			column = "site_group->>'groupName'"
		case facilities.SearchFacilityRequest_group_name_desc:
			column = "site_group->>'groupName' DESC"
		default:
			var ok bool
			column, ok = strings.CutSuffix(facilities.SearchFacilityRequest_Order_name[int32(order)], "_desc")
			if ok {
				column += " DESC"
			} else {
				column, _ = strings.CutSuffix(facilities.SearchFacilityRequest_Order_name[int32(order)], "_asc")
			}
		}
		query.OrderExpr(column + " NULLS LAST")
	}

	// 조회 결과 제한
	if req.Limit > 0 {
		query.Limit(int(req.Limit)).Offset(int(req.Offset))
	}

	// 조회
	if err := query.ForEach(func(tuple *facilities.Facility) error {
		res.Entities = append(res.Entities, proto.Clone(tuple).(*facilities.Facility))
		tuple = nil
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}
	if res.Count == 0 {
		res.Count = uint64(len(res.Entities))
	}

	sdlmicro.SetPagination(ctx, req.Limit, req.Offset, res.Count, res.Link)
	return res, nil
}
